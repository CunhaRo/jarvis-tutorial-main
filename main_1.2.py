"""
Jarvis - Versão 1.0 (Com Gemini)
"""

import os
import pyttsx3
import speech_recognition as sr
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

VELOCIDADE_FALA = 200
PAUSA_SILENCIO = 1.2


class Jarvis:
    def __init__(self, chave):
        # Aponta o cliente OpenAI para o endpoint oficial do Google AI Studio
        self.cliente = OpenAI(
            api_key=chave,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        self.reconhecedor = sr.Recognizer()
        self.microfone = sr.Microphone()

        self.reconhecedor.pause_threshold = PAUSA_SILENCIO

        print("Calibrando microfone... Aguarde.")
        with self.microfone as fonte:
            self.reconhecedor.adjust_for_ambient_noise(fonte, duration=2)
            print(f"Microfone calibrado! Nível de ruído: {self.reconhecedor.energy_threshold}")

        print("✅ Configuração do microfone concluída.")

    def ouvir(self):
        with self.microfone as fonte:
            print("\n🎙️ Ouvindo...")
            try:
                audio = self.reconhecedor.listen(fonte, timeout=10, phrase_time_limit=10)
                texto = self.reconhecedor.recognize_google(audio, language="pt-BR")
                print(f"Você disse: {texto}")
                return texto
            except sr.UnknownValueError:
                print("🤖 JARVIS não compreendeu o áudio.")
                return None
            except sr.RequestError as e:
                print(f"Erro no serviço de reconhecimento: {e}")
                return None

    def pensar(self, texto):
        try:
            resposta = self.cliente.chat.completions.create(
                model=GEMINI_MODEL,
                messages=[
                    {"role": "system", "content": "Você é um assistente pessoal chamado JARVIS. Responda de forma concisa, direta e natural."},
                    {"role": "user", "content": texto}
                ]
            )
            texto_resposta = resposta.choices[0].message.content.strip()
            print(f"JARVIS: {texto_resposta}")
            return texto_resposta
        except Exception as e:
            print(f"Erro na API do Gemini: {e}")
            return "Desculpe, ocorreu um erro ao processar sua solicitação."

    def falar(self, texto):
        motor = None
        try:
            motor = pyttsx3.init()
            vozes = motor.getProperty('voices')
            for voz in vozes:
                if "brazil" in voz.name.lower() or "portuguese" in voz.name.lower():
                    motor.setProperty('voice', voz.id)
                    break

            motor.setProperty('rate', VELOCIDADE_FALA)
            motor.say(texto)
            motor.runAndWait()
            motor.stop()
        except Exception as e:
            print(f"Erro na síntese de voz: {e}")
        finally:
            if motor:
                try:
                    del motor
                except Exception:
                    pass

    def executar(self):
        print("=" * 60)
        print("🤖 JARVIS (Gemini) Inicializado")
        print("Diga 'sair' para encerrar")
        print("=" * 60)

        while True:
            texto = self.ouvir()

            if not texto:
                continue

            if texto.lower().strip() in ["sair", "desligar", "fechar"]:
                print("\n🤖 JARVIS encerrando atividades...")
                self.falar("Até logo!")
                break

            resposta = self.pensar(texto)
            self.falar(resposta)
            print("=" * 60)


def main():
    chave = os.getenv("GEMINI_API_KEY")

    if not chave:
        print("⚠️ Chave GEMINI_API_KEY não encontrada no arquivo .env.")
        return

    try:
        jarvis = Jarvis(chave)
        jarvis.executar()
    except KeyboardInterrupt:
        print("\nProcesso interrompido.")
    except Exception as e:
        print(f"Erro geral: {e}")


if __name__ == "__main__":
    main()