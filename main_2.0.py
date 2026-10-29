"""
JARVIS v5
Full-Duplex + Gemini (via OpenAI Compatibility) + gTTS + Orquestrador de Tools + Memória Persistente
"""

import os
import sys
import time
import json
import queue
import tempfile
import threading
from pathlib import Path

import numpy as np
import pyaudio
import pygame
import speech_recognition as sr
from dotenv import load_dotenv
from gtts import gTTS
from openai import OpenAI  # Adicionado

from tools.jarvis_memoria import JarvisMemoria

# Importa o orquestrador diretamente
sys.path.insert(0, str(Path(__file__).parent))
from tools.orquestrador_tools import OrquestradorDeTools

load_dotenv()

# ========== CONFIGURAÇÕES ==========
LIMIAR_INTERRUPCAO = 1500
TAXA_AMOSTRAGEM = 16000
TAMANHO_CHUNK = 1024
MODELO_GEMINI = "gemini-3.8-flash"

# Memória
LIMITE_HISTORICO = 50  # Últimas mensagens carregadas do banco
# ===================================

pygame.mixer.init()


class ClienteOrquestrador:
    """Cliente do Orquestrador de Tools - Usa importação direta"""
    
    def __init__(self):
        print("🔌 Iniciando Orquestrador de Tools...")
        self.orquestrador = OrquestradorDeTools()
        ferramentas = list(self.orquestrador.ferramentas.keys())
        print(f"✅ Orquestrador pronto! Ferramentas: {', '.join(ferramentas)}")
        self.ferramentas = None
    
    def listar_ferramentas(self) -> list:
        self.ferramentas = self.orquestrador.obter_lista_ferramentas()
        return self.ferramentas
    
    def chamar_ferramenta(self, nome: str, argumentos: dict) -> any:
        resposta = self.orquestrador.chamar_ferramenta(nome, argumentos)
        if resposta.get("error"):
            print(f"❌ Erro na ferramenta {nome}: {resposta['error']}")
            return None
        return resposta.get("result")
    
    def fechar(self):
        print("🔌 Orquestrador finalizado")


class JarvisComMemoria:
    """JARVIS v5 - Memória Persistente + Personalização + Gemini"""
    
    def __init__(self, chave_api):
        print("🔧 Iniciando JARVIS v5...")
        self.cliente = OpenAI(
            api_key=chave_api, 
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        print("   ✓ GEMINI cliente criado via compatibilidade OpenAI")
        self.reconhecedor = sr.Recognizer()
        self.pyaudio = pyaudio.PyAudio()
        
        # Inicializa MEMÓRIA
        print("   → Iniciando memória...")
        self.memoria = JarvisMemoria()
        self.sessao_id = self.memoria.iniciar_sessao()
        self.contador_mensagens = 0
        print(f"   ✓ Memória iniciada (sessão #{self.sessao_id})")
        
        # Inicia cliente do orquestrador
        print("   → Iniciando orquestrador...")
        self.orquestrador = ClienteOrquestrador()
        self.ferramentas_disponiveis = self.orquestrador.listar_ferramentas()
        print(f"   ✓ {len(self.ferramentas_disponiveis)} ferramentas carregadas")
        
        # Controle de estado
        self.falando = False
        self.interromper = threading.Event()
        self.executando = True
        self.buffer_audio = []
        self.trava_audio = threading.Lock()
        self.comando_interrompido = None
        
        # Configuração de microfone
        self.reconhecedor.energy_threshold = 150
        self.reconhecedor.dynamic_energy_threshold = True
        self.reconhecedor.pause_threshold = 2.0
        self.reconhecedor.non_speaking_duration = 0.8
        
        self.nome_usuario = self.memoria.obter_nome_usuario()
        
        # Histórico da sessão
        self.historico = [
            {"role": "system", "content": self._criar_prompt_sistema()}
        ]
        
        historico_banco = self.memoria.obter_historico_recente(LIMITE_HISTORICO)
        if historico_banco:
            print(f"   ✓ Carregadas {len(historico_banco)} mensagens do histórico")
            self.historico.extend(historico_banco)
        else:
            print("   ⚠️ Nenhuma mensagem anterior no histórico")
        
        print("🎤 JARVIS v5 pronto para operação.")
        if self.nome_usuario:
            print(f"👤 Usuário identificado: {self.nome_usuario}")
        print("=" * 50)
    
    def _criar_prompt_sistema(self) -> str:
        nome = self.nome_usuario or "o usuário"
        
        prompt = f"""Você é JARVIS, um assistente inteligente pessoal, divertido e sarcástico.
Você está conversando com {nome}.

IMPORTANTE: Você TEM MEMÓRIA das conversas anteriores no histórico.
Seja amigável e use o nome do usuário nas respostas quando apropriado. Responda em português de forma concisa e natural.

Quando precisar usar uma ferramenta, responda APENAS o JSON com o formato EXATO abaixo:
{{
    "tool": "nome_exato_da_ferramenta",
    "arguments": {{"param1": "valor1"}}
}}

Ferramentas disponíveis:
"""
        for ferramenta in self.ferramentas_disponiveis:
            prompt += f"\n{ferramenta['name']}: {ferramenta['description']}"
            parametros = ferramenta.get('parameters', {})
            if parametros:
                prompt += f"\n  Parâmetros: {', '.join(parametros.keys())}"
        
        prompt += f"""

Instruções finais:
1. Use ferramentas quando apropriado (cálculos, horários, buscas).
2. Após receber o resultado da ferramenta, responda naturalmente.
3. Se não precisar de ferramenta, responda diretamente em texto plano.
4. Mantenha respostas curtas e objetivas para sintetização de voz.
"""
        return prompt
    
    def _perguntar_nome(self):
        print("\n" + "=" * 50)
        print("🎉 BEM-VINDO AO JARVIS!")
        print("=" * 50)
        
        self.falar("Olá! Eu sou o JARVIS, seu assistente pessoal.")
        time.sleep(0.5)
        self.falar("Como devo te chamar?")
        
        tentativas = 0
        while tentativas < 3:
            nome = self.ouvir()
            if nome:
                self.falar(f"Deixa eu confirmar: seu nome é {nome}?")
                confirmacao = self.ouvir()
                
                if confirmacao and any(p in confirmacao.lower() for p in ['sim', 'isso', 'correto', 'é', 'exato']):
                    self.nome_usuario = nome
                    self.memoria.salvar_nome_usuario(nome)
                    self.historico[0]["content"] = self._criar_prompt_sistema()
                    
                    saudacao = self.memoria.obter_saudacao_contextual(nome)
                    self.falar(f"{saudacao}! É um prazer falar com você, {nome}!")
                    return
                else:
                    self.falar("Tudo bem, qual é o seu nome então?")
            
            tentativas += 1
        
        self.falar("Sem problemas, continuaremos por enquanto sem definir o nome.")
    
    def monitorar_audio(self):
        fluxo = self.pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=TAXA_AMOSTRAGEM,
            input=True,
            frames_per_buffer=TAMANHO_CHUNK
        )
        
        contagem_alta = 0
        CONTAGEM_MINIMA = 3
        gravando_interrupcao = False
        frames_interrupcao = []
        frames_silencio = 0
        FRAMES_SILENCIO_MAX = 15
        
        try:
            while self.executando:
                dados = fluxo.read(TAMANHO_CHUNK, exception_on_overflow=False)
                dados_audio = np.frombuffer(dados, dtype=np.int16)
                nivel = np.abs(dados_audio).mean()
                
                if self.falando:
                    with self.trava_audio:
                        self.buffer_audio.append(dados)
                        max_frames = int(5 * TAXA_AMOSTRAGEM / TAMANHO_CHUNK)
                        if len(self.buffer_audio) > max_frames:
                            self.buffer_audio.pop(0)
                    
                    if nivel > LIMIAR_INTERRUPCAO:
                        contagem_alta += 1
                        if contagem_alta >= CONTAGEM_MINIMA and not self.interromper.is_set():
                            print(f"🛑 INTERRUPÇÃO! Nível: {nivel:.0f}")
                            self.interromper.set()
                            pygame.mixer.music.stop()
                            gravando_interrupcao = True
                            frames_interrupcao = list(self.buffer_audio)
                    else:
                        contagem_alta = 0
                
                if gravando_interrupcao:
                    frames_interrupcao.append(dados)
                    if nivel < LIMIAR_INTERRUPCAO / 2:
                        frames_silencio += 1
                    else:
                        frames_silencio = 0
                    
                    if frames_silencio >= FRAMES_SILENCIO_MAX:
                        gravando_interrupcao = False
                        frames_silencio = 0
                        
                        bytes_audio = b''.join(frames_interrupcao)
                        audio_sr = sr.AudioData(bytes_audio, TAXA_AMOSTRAGEM, 2)
                        
                        try:
                            texto = self.reconhecedor.recognize_google(audio_sr, language='pt-BR')
                            print(f"👤 Interrupção: {texto}")
                            self.comando_interrompido = texto
                        except Exception:
                            self.comando_interrompido = None
                        
                        frames_interrupcao = []
                
                time.sleep(0.03)
        finally:
            fluxo.stop_stream()
            fluxo.close()
    
    def ouvir(self):
        print("\n🎧 Ouvindo...")
        mic = sr.Microphone()
        with mic as source:
            self.reconhecedor.adjust_for_ambient_noise(source, duration=0.3)
            try:
                audio = self.reconhecedor.listen(source, timeout=15, phrase_time_limit=30)
                texto = self.reconhecedor.recognize_google(audio, language='pt-BR')
                print(f"👤 Você: {texto}")
                return texto
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except Exception as e:
                print(f"❌ Erro de áudio: {e}")
                return None
    
    def pensar(self, comando):
        print("🤖 Processando...")
        self.historico.append({"role": "user", "content": comando})
        self.memoria.adicionar_mensagem("user", comando)
        self.contador_mensagens += 1
        
        try:
            resposta = self.cliente.chat.completions.create(
                model=MODELO_GEMINI,
                messages=self.historico
            )
            
            texto_resposta = resposta.choices[0].message.content
            
            if self._e_chamada_ferramenta(texto_resposta):
                print("🛠️ Chamada de ferramenta identificada...")
                resultado = self._executar_ferramenta(texto_resposta)
                
                self.historico.append({"role": "assistant", "content": texto_resposta})
                
                if resultado is not None:
                    self.historico.append({
                        "role": "user", 
                        "content": f"[RESULTADO DA FERRAMENTA]: {resultado}\n\nResponda diretamente ao usuário usando esses dados."
                    })
                else:
                    self.historico.append({
                        "role": "user",
                        "content": "[ERRO]: Falha na execução da ferramenta. Informe o usuário sucintamente."
                    })
                
                resposta2 = self.cliente.chat.completions.create(
                    model=MODELO_GEMINI,
                    messages=self.historico
                )
                
                resposta_final = resposta2.choices[0].message.content
                self.historico.append({"role": "assistant", "content": resposta_final})
                self.memoria.adicionar_mensagem("assistant", resposta_final)
                self.contador_mensagens += 1
                return resposta_final
            
            self.historico.append({"role": "assistant", "content": texto_resposta})
            self.memoria.adicionar_mensagem("assistant", texto_resposta)
            self.contador_mensagens += 1
            return texto_resposta
            
        except Exception as e:
            print(f"❌ Erro na API do Gemini: {e}")
            resposta_erro = "Desculpe, tive um problema ao processar sua solicitação."
            self.memoria.adicionar_mensagem("assistant", resposta_erro)
            return resposta_erro
    
    def _e_chamada_ferramenta(self, texto: str) -> bool:
        texto = texto.strip()
        return '{' in texto and '"tool"' in texto and '"arguments"' in texto
    
    def _executar_ferramenta(self, texto_json: str) -> any:
        try:
            inicio = texto_json.find('{')
            fim = texto_json.rfind('}') + 1
            if inicio == -1 or fim == 0:
                return None
            
            chamada = json.loads(texto_json[inicio:fim])
            nome = chamada.get("tool")
            args = chamada.get("arguments", {})
            
            print(f"   🔧 Executando {nome} com args: {args}")
            return self.orquestrador.chamar_ferramenta(nome, args)
        except Exception as e:
            print(f"   ❌ Falha ao decodificar JSON da tool: {e}")
            return None
    
    def falar(self, texto):
        print(f"🔊 JARVIS: {texto}\n")
        self.falando = True
        self.interromper.clear()
        self.comando_interrompido = None
        
        with self.trava_audio:
            self.buffer_audio = []
        
        arquivo_audio = os.path.join(tempfile.gettempdir(), "jarvis_fala.mp3")
        
        try:
            tts = gTTS(text=texto, lang='pt-br')
            tts.save(arquivo_audio)
            
            pygame.mixer.music.load(arquivo_audio)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                if self.interromper.is_set():
                    pygame.mixer.music.stop()
                    print("🛑 Reprodução interrompida.")
                    break
                time.sleep(0.05)
        except Exception as e:
            print(f"❌ Erro na síntese de voz: {e}")
        finally:
            self.falando = False
            try:
                if os.path.exists(arquivo_audio):
                    pygame.mixer.music.unload()
                    os.remove(arquivo_audio)
            except Exception:
                pass
        
        if self.interromper.is_set():
            time.sleep(0.5)
        return self.interromper.is_set()

    def executar(self):
        print("=" * 50)
        print("🤖 JARVIS v5 - ONLINE")
        print("=" * 50)
        
        monitor = threading.Thread(target=self.monitorar_audio, daemon=True)
        monitor.start()
        time.sleep(0.5)
        
        if not self.nome_usuario:
            self._perguntar_nome()
        else:
            saudacao = self.memoria.obter_saudacao_contextual(self.nome_usuario)
            self.falar(f"{saudacao}! Como posso ajudar?")
        
        while self.executando:
            if self.comando_interrompido:
                comando = self.comando_interrompido
                self.comando_interrompido = None
                print(f"🔄 Retomando com comando: {comando}")
            else:
                comando = self.ouvir()
            
            if not comando:
                continue
            
            comando_lower = comando.lower()
            
            if any(p in comando_lower for p in ['sair', 'desligar', 'tchau', 'encerrar']):
                nome = self.nome_usuario or ""
                self.falar(f"Até mais, {nome}! Encerrando atividades.")
                self.executando = False
                break
            
            if 'limpar memória' in comando_lower or 'esquecer tudo' in comando_lower:
                self.falar("Deseja realmente apagar o histórico de conversas anteriores?")
                conf = self.ouvir()
                if conf and 'sim' in conf.lower():
                    self.memoria.limpar_historico()
                    self.historico = [{"role": "system", "content": self._criar_prompt_sistema()}]
                    self.falar("Memória limpa com sucesso.")
                else:
                    self.falar("Operação cancelada, mantendo histórico.")
                continue
            
            if 'exportar' in comando_lower and 'histórico' in comando_lower:
                arquivo = self.memoria.exportar_historico()
                self.falar(f"Histórico exportado com sucesso.")
                continue
            
            resposta = self.pensar(comando)
            self.falar(resposta)
        
        # Cleanup
        self.memoria.finalizar_sessao(self.sessao_id, self.contador_mensagens)
        self.memoria.fechar()
        self.orquestrador.fechar()
        self.pyaudio.terminate()
        pygame.mixer.quit()
        print("\n👋 JARVIS offline.")


def main():
    chave_api = os.getenv("GEMINI_API_KEY")
    if not chave_api:
        print("⚠️ Variável GEMINI_API_KEY não encontrada no arquivo .env")
        return
    
    try:
        jarvis = JarvisComMemoria(chave_api)
        jarvis.executar()
    except KeyboardInterrupt:
        print("\n\n👋 Finalizado pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro de inicialização: {e}")


if __name__ == "__main__":
    main()