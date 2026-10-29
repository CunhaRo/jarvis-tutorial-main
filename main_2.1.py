"""
Versão 2.0 (Com OpenAI)
Full-Duplex + OpenAI (via OpenAI Compatibility) + TTS + Orquestrador de Tools + Memória Persistente
Original pertence a: https://github.com/eai-academy/jarvis-tutorial

"""

import speech_recognition as sr
from openai import OpenAI
import pyaudio
import pygame
import numpy as np
import os
import threading
import time
import tempfile
import queue
import json
from pathlib import Path
from dotenv import load_dotenv
from tools.jarvis_memoria import JarvisMemoria

# Importa o orquestrador diretamente
import sys
sys.path.insert(0, str(Path(__file__).parent))
from tools.orquestrador_tools import OrquestradorDeTools

load_dotenv()

# ========== CONFIGURAÇÕES ==========
LIMIAR_INTERRUPCAO = 1500
TAXA_AMOSTRAGEM = 16000
TAMANHO_CHUNK = 1024

# OpenAI TTS
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "shimmer"

# Memória
LIMITE_HISTORICO = 50  # Últimas 50 mensagens carregadas do banco
# ===================================

pygame.mixer.init()


class ClienteOrquestrador:
    """Cliente do Orquestrador de Tools - Usa importação direta"""
    
    def __init__(self):
        """Inicializa o orquestrador diretamente"""
        print("🔌 Iniciando Orquestrador de Tools...")
        
        self.orquestrador = OrquestradorDeTools()

        ferramentas = list(self.orquestrador.ferramentas.keys())
        print(f"✅ Orquestrador pronto! Ferramentas: {', '.join(ferramentas)}")
        self.ferramentas = None
    
    def listar_ferramentas(self) -> list:
        """Lista todas as ferramentas disponíveis"""
        self.ferramentas = self.orquestrador.obter_lista_ferramentas()
        return self.ferramentas
    
    def chamar_ferramenta(self, nome: str, argumentos: dict) -> any:
        """Chama uma ferramenta pelo nome"""
        resposta = self.orquestrador.chamar_ferramenta(nome, argumentos)
        
        if resposta.get("error"):
            print(f"❌ Erro na ferramenta {nome}: {resposta['error']}")
            return None
        
        return resposta.get("result")
    
    def fechar(self):
        """Cleanup"""
        print("🔌 Orquestrador finalizado")


class JarvisComMemoria:
    """JARVIS v5 - v4 + Memória Persistente + Personalização"""
    
    def __init__(self, chave_api):
        print("🔧 Iniciando JARVIS v5...")
        self.cliente = OpenAI(api_key=chave_api)
        print("   ✓ OpenAI cliente criado")
        self.reconhecedor = sr.Recognizer()
        print("   ✓ Reconhecedor criado")
        self.pyaudio = pyaudio.PyAudio()
        print("   ✓ PyAudio criado")
        
        # NOVO v5: Inicializa MEMÓRIA
        print("   → Iniciando memória...")
        self.memoria = JarvisMemoria()
        self.sessao_id = self.memoria.iniciar_sessao()
        self.contador_mensagens = 0
        print(f"   ✓ Memória iniciada (sessão #{self.sessao_id})")
        
        # Inicia cliente do orquestrador
        print("   → Iniciando orquestrador...")
        self.orquestrador = ClienteOrquestrador()
        print("   ✓ Orquestrador criado")
        print("   → Listando ferramentas...")
        self.ferramentas_disponiveis = self.orquestrador.listar_ferramentas()
        print(f"   ✓ {len(self.ferramentas_disponiveis)} ferramentas carregadas")
        
        # Controle de estado (igual v4)
        self.falando = False
        self.interromper = threading.Event()
        self.executando = True
        self.buffer_audio = []
        self.trava_audio = threading.Lock()
        self.comando_interrompido = None
        
        # Configura reconhecimento
        self.reconhecedor.energy_threshold = 150
        self.reconhecedor.dynamic_energy_threshold = True
        self.reconhecedor.pause_threshold = 2.0
        self.reconhecedor.non_speaking_duration = 0.8
        
        # NOVO v5: Carrega nome do usuário (se existir)
        self.nome_usuario = self.memoria.obter_nome_usuario()
        
        # Histórico da sessão atual (memória RAM)
        self.historico = [
            {"role": "system", "content": self._criar_prompt_sistema()}
        ]
        
        # NOVO v5: Carrega histórico recente do banco
        historico_banco = self.memoria.obter_historico_recente(LIMITE_HISTORICO)
        if historico_banco:
            print(f"   ✓ Carregadas {len(historico_banco)} mensagens do histórico")
            print(f"   📝 Primeira: {historico_banco[0]['content'][:50]}...")
            print(f"   📝 Última: {historico_banco[-1]['content'][:50]}...")
            self.historico.extend(historico_banco)
        else:
            print(f"   ⚠️ Nenhuma mensagem no histórico")
        
        print("🎤 JARVIS v5 - Memória Persistente + Personalização!")
        print(f"🔊 Voz: {TTS_VOICE} | Modelo: {TTS_MODEL}")
        print(f"🛠️ Ferramentas: {len(self.ferramentas_disponiveis)}")
        if self.nome_usuario:
            print(f"👤 Usuário: {self.nome_usuario}")
        print("=" * 50)
    
    def _criar_prompt_sistema(self) -> str:
        """Cria o prompt do sistema com ferramentas e personalização"""
        
        # NOVO v5: Personalização com nome
        nome = self.nome_usuario or "o usuário"
        
        prompt = f"""Você é JARVIS, um assistente inteligente pessoal, divertido e sarcástico.
Você está conversando com {nome}.

IMPORTANTE: Você TEM MEMÓRIA das conversas anteriores! O histórico de mensagens está disponível acima.
Você pode se referir a conversas passadas, ferramentas que já usou, e coisas que o usuário já te pediu.

Seja amigável, use o nome do usuário nas respostas quando apropriado.
Responda em português de forma concisa e natural.

Quando precisar usar uma ferramenta, responda APENAS o JSON com o formato EXATO abaixo:
{{
    "tool": "nome_exato_da_ferramenta",
    "arguments": {{"param1": "valor1"}}
}}

IMPORTANTE: Use o nome EXATO da ferramenta conforme listado abaixo.

Ferramentas disponíveis:
"""
        
        for ferramenta in self.ferramentas_disponiveis:
            prompt += f"\n- {ferramenta['name']}: {ferramenta['description']}"
            parametros = ferramenta.get('parameters', {})
            if parametros:
                prompt += f"\n  Parâmetros: {', '.join(parametros.keys())}"
        
        prompt += f"""

IMPORTANTE:
1. Use ferramentas quando apropriado (horário, cálculos, clima, buscas)
2. Após receber resultado da ferramenta, responda naturalmente ao usuário
3. Se não precisar de ferramenta, responda normalmente
4. Use o nome "{nome}" para personalizar respostas
5. Mantenha respostas curtas e objetivas
"""
        return prompt
    
    def _perguntar_nome(self):
        """NOVO v5: Primeira execução - pergunta o nome do usuário"""
        print("\n" + "=" * 50)
        print("🎉 BEM-VINDO AO JARVIS!")
        print("=" * 50)
        
        self.falar("Olá! Eu sou o JARVIS, seu assistente pessoal. Prazer em conhecê-lo!")
        time.sleep(0.5)
        self.falar("Para começarmos, qual é o seu nome?")
        
        # Escuta o nome
        tentativas = 0
        while tentativas < 3:
            nome = self.ouvir()
            
            if nome:
                # Confirma o nome
                self.falar(f"Deixa eu confirmar: seu nome é {nome}?")
                confirmacao = self.ouvir()
                
                if confirmacao and any(p in confirmacao.lower() for p in ['sim', 'isso', 'correto', 'é', 'exato']):
                    self.nome_usuario = nome
                    self.memoria.salvar_nome_usuario(nome)
                    
                    # Atualiza system prompt com o nome
                    self.historico[0]["content"] = self._criar_prompt_sistema()
                    
                    saudacao = self.memoria.obter_saudacao_contextual(nome)
                    self.falar(f"{saudacao} É um prazer te conhecer, {nome}!")
                    return
                else:
                    self.falar("Ok, vamos tentar novamente. Qual é o seu nome?")
            
            tentativas += 1
        
        # Se não conseguiu o nome após 3 tentativas
        self.falar("Tudo bem, vamos começar sem o nome por enquanto. Você pode me dizer depois!")
    
    def monitorar_audio(self):
        """Thread que monitora áudio (idêntico v4)"""
        print("👂 Monitor de áudio iniciado")
        
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
                            print(f"👤 Interrupção capturada: {texto}")
                            self.comando_interrompido = texto
                        except:
                            print("❓ Não entendi a interrupção")
                            self.comando_interrompido = None
                        
                        frames_interrupcao = []
                
                time.sleep(0.03)
                
        finally:
            fluxo.stop_stream()
            fluxo.close()
    
    def ouvir(self):
        """Captura comando de voz (idêntico v4)"""
        print("\n🎧 Fale seu comando...")
        
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
                print("❓ Não entendi...")
                return None
            except Exception as e:
                print(f"❌ Erro: {e}")
                return None
    
    def pensar(self, comando):
        """
        Processa comando com OpenAI - detecta e executa ferramentas
        NOVO v5: Salva mensagens na memória persistente
        """
        print("🤖 Processando...")
        
        # Adiciona comando do usuário ao histórico (RAM e BANCO)
        self.historico.append({"role": "user", "content": comando})
        self.memoria.adicionar_mensagem("user", comando)
        self.contador_mensagens += 1
        
        try:
            # Chama OpenAI
            resposta = self.cliente.chat.completions.create(
                model="gpt-5-mini",
                messages=self.historico
            )
            
            texto_resposta = resposta.choices[0].message.content
            
            # Verifica se é uma chamada de ferramenta
            if self._e_chamada_ferramenta(texto_resposta):
                print("🛠️ Detectada chamada de ferramenta...")
                resultado = self._executar_ferramenta(texto_resposta)
                
                # Adiciona a tentativa ao histórico (apenas RAM, não salva no banco)
                self.historico.append({"role": "assistant", "content": texto_resposta})
                
                if resultado is not None:
                    # Sucesso - adiciona resultado e pede resposta natural
                    self.historico.append({
                        "role": "user", 
                        "content": f"[RESULTADO DA FERRAMENTA]: {resultado}\n\nAgora responda naturalmente ao usuário sobre isso."
                    })
                else:
                    # Erro - informa o GPT
                    self.historico.append({
                        "role": "user",
                        "content": "[ERRO]: A ferramenta falhou. Informe o usuário que houve um problema e você não conseguiu executar a ação."
                    })
                
                # Nova chamada para resposta final
                resposta2 = self.cliente.chat.completions.create(
                    model="gpt-5-mini",
                    messages=self.historico
                )
                
                resposta_final = resposta2.choices[0].message.content
                
                # Salva resposta final (RAM e BANCO)
                self.historico.append({"role": "assistant", "content": resposta_final})
                self.memoria.adicionar_mensagem("assistant", resposta_final)
                self.contador_mensagens += 1
                
                return resposta_final
            
            # Resposta normal (RAM e BANCO)
            self.historico.append({"role": "assistant", "content": texto_resposta})
            self.memoria.adicionar_mensagem("assistant", texto_resposta)
            self.contador_mensagens += 1
            
            return texto_resposta
            
        except Exception as e:
            print(f"❌ Erro OpenAI: {e}")
            resposta_erro = "Desculpe, tive um problema técnico."
            self.memoria.adicionar_mensagem("assistant", resposta_erro)
            return resposta_erro
    
    def _e_chamada_ferramenta(self, texto: str) -> bool:
        """Detecta se a resposta é uma chamada de ferramenta (formato JSON)"""
        texto = texto.strip()
        # Aceita qualquer JSON que tenha "tool" e "arguments"
        return ('{' in texto and 
                '"tool"' in texto and 
                '"arguments"' in texto)
    
    def _executar_ferramenta(self, texto_json: str) -> any:
        """Executa ferramenta via Orquestrador"""
        try:
            # Extrai o JSON da resposta (caso tenha texto antes/depois)
            inicio = texto_json.find('{')
            fim = texto_json.rfind('}') + 1
            
            if inicio == -1 or fim == 0:
                print("   ❌ JSON não encontrado na resposta")
                return None
            
            json_extraido = texto_json[inicio:fim]
            chamada = json.loads(json_extraido)
            
            nome_ferramenta = chamada.get("tool")
            argumentos = chamada.get("arguments", {})
            
            print(f"   🔧 Chamando: {nome_ferramenta}")
            print(f"   📋 Args: {argumentos}")
            
            # Chama via Orquestrador
            resultado = self.orquestrador.chamar_ferramenta(nome_ferramenta, argumentos)
            
            print(f"   ✅ Resultado: {resultado}")
            return resultado
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def falar(self, texto):
        """Fala usando OpenAI TTS (idêntico v4)"""
        print(f"🔊 JARVIS: {texto}\n")
        
        self.falando = True
        self.interromper.clear()
        self.comando_interrompido = None
        
        with self.trava_audio:
            self.buffer_audio = []
        
        arquivo_audio = os.path.join(tempfile.gettempdir(), "jarvis_fala.mp3")
        
        try:
            # Streaming recomendado pela OpenAI
            with self.cliente.audio.speech.with_streaming_response.create(
                model=TTS_MODEL,
                voice=TTS_VOICE,
                input=texto,
                instructions="Speak in a cheerful and positive tone.",
            ) as response:
                response.stream_to_file(arquivo_audio)
            
            pygame.mixer.music.load(arquivo_audio)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                if self.interromper.is_set():
                    pygame.mixer.music.stop()
                    print("🛑 Fala interrompida!")
                    break
                time.sleep(0.05)
            
        except Exception as e:
            print(f"❌ Erro na fala: {e}")
        
        finally:
            self.falando = False
            try:
                if os.path.exists(arquivo_audio):
                    pygame.mixer.music.unload()
                    os.remove(arquivo_audio)
            except:
                pass
        
        if self.interromper.is_set():
            time.sleep(1.0)
        
        return self.interromper.is_set()
    
    def executar(self):
        """Loop principal - NOVO v5: com personalização e comandos de memória"""
        print("=" * 50)
        print("🤖 JARVIS v5 - VERSÃO FINAL")
        print("=" * 50)
        print("✨ Memória persistente entre sessões")
        print("✨ Personalização com seu nome")
        print("✨ Ferramentas + Full-Duplex")
        print("✨ Diga 'sair' para encerrar")
        print("=" * 50)
        
        # Inicia monitor de áudio
        monitor = threading.Thread(target=self.monitorar_audio, daemon=True)
        monitor.start()
        time.sleep(1)
        
        # NOVO v5: PRIMEIRA VEZ - Pergunta o nome
        if not self.nome_usuario:
            self._perguntar_nome()
        else:
            # NOVO v5: JÁ CONHECE - Saudação personalizada
            saudacao = self.memoria.obter_saudacao_contextual(self.nome_usuario)
            self.falar(f"{saudacao} Como posso te ajudar hoje?")
        
        # Loop principal
        while self.executando:
            # Verifica comando de interrupção
            if self.comando_interrompido:
                comando = self.comando_interrompido
                self.comando_interrompido = None
                print(f"🔄 Usando comando da interrupção: {comando}")
            else:
                comando = self.ouvir()
            
            if not comando:
                continue
            
            # Comandos especiais
            comando_lower = comando.lower()
            
            # Sair
            if any(p in comando_lower for p in ['sair', 'desligar', 'tchau', 'encerrar']):
                nome = self.nome_usuario or "amigo"
                self.falar(f"Até logo, {nome}! Foi um prazer conversar com você!")
                self.executando = False
                break
            
            # NOVO v5: Limpar memória
            if 'limpar memória' in comando_lower or 'esquecer tudo' in comando_lower:
                self.falar("Tem certeza que quer que eu esqueça nossas conversas anteriores?")
                confirmacao = self.ouvir()
                if confirmacao and 'sim' in confirmacao.lower():
                    self.memoria.limpar_historico()
                    self.historico = [{"role": "system", "content": self._criar_prompt_sistema()}]
                    self.falar("Ok, memória limpa. Começamos do zero!")
                else:
                    self.falar("Ok, vou manter tudo guardado!")
                continue
            
            # NOVO v5: Exportar histórico
            if 'exportar' in comando_lower and 'histórico' in comando_lower:
                arquivo = self.memoria.exportar_historico()
                self.falar(f"Histórico exportado para {arquivo}!")
                continue
            
            # Processa comando normalmente (pode usar ferramentas)
            resposta = self.pensar(comando)
            self.falar(resposta)
        
        # NOVO v5: Cleanup e estatísticas
        print("\n" + "=" * 50)
        print("📊 ESTATÍSTICAS DA SESSÃO")
        print("=" * 50)
        print(f"💬 Mensagens nesta sessão: {self.contador_mensagens}")
        
        resumo = self.memoria.obter_resumo_historico()
        print(f"💾 Total no histórico: {resumo['total_mensagens']} mensagens")
        print(f"📅 Primeira mensagem: {resumo.get('primeira_mensagem', 'N/A')}")
        
        self.memoria.finalizar_sessao(self.sessao_id, self.contador_mensagens)
        self.memoria.fechar()
        
        self.orquestrador.fechar()
        self.pyaudio.terminate()
        pygame.mixer.quit()
        
        print("\n👋 JARVIS encerrado!")


def main():
    chave_api = os.getenv("OPENAI_API_KEY")
    
    if not chave_api:
        print("⚠️ Configure OPENAI_API_KEY no arquivo .env")
        return
    
    try:
        jarvis = JarvisComMemoria(chave_api)
        jarvis.executar()
    except KeyboardInterrupt:
        print("\n\n👋 Interrompido")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()