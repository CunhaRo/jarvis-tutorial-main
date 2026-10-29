# 🤖 Assistente Virtual Inteligente -Jarvis

Full-Duplex + Gemini + gTTS + Orquestrador de Tools + Memória Persistente

Assistente virtual completo construído com Python, OpenAI e GEMINI e recursos de reconhecimento de voz.

Assistente de voz em Python com suporte a **OpenAI** e **Google Gemini**, conversação **Full-Duplex** (permite interromper a fala do assistente), **memória persistente (SQLite)** e **ferramentas integradas (Tools)**.
## 🎯 Como Usar

### Comandos Básicos (Todas as Versões)

- Fale naturalmente com o JARVIS
- Diga "sair", "tchau" ou "adeus" para encerrar
- O JARVIS responde a qualquer pergunta via GPT

### Recursos Específicos v4

- **Memória:** "O que conversamos antes?"
- **Clima:** "Como está o clima em São Paulo?"
- **Hora:** "Que horas são?"
- **Busca:** "Busque informações sobre Python"
- **Arquivos:** "Crie um arquivo teste.txt"

---


Cada versão mantém as funcionalidades da anterior e adiciona novas capacidades.

---

## 📚 Estrutura do Projeto

```
jarvis-tutorial/
│
├── main_1.py              # Versão 1 - Básico
├── main_2.py              # Versão 2 - Mais complets

│
├── tools/                  # Sistema de ferramentas (v4)
│   ├── __init__.py
│   ├── orquestrador_tools.py
│   ├── clima.py
│   ├── hora.py
│   ├── buscar_web.py
│   ├── sistema_arquivos.py
│   ├── jarvis_memoria.py
│   └── README.md
│
├── requirements.txt        # Dependências
├── .env                    # Configurações (não versionado)
├── .gitignore
└── README.md              # Este arquivo
```

---

## 🔑 Obtendo Chaves de API

### OpenAI (Obrigatória)

1. Acesse: https://platform.openai.com/
2. Crie uma conta
3. Vá em "API Keys"
4. Crie uma nova chave

### Perplexity AI (Opcional - v4)

1. Acesse: https://www.perplexity.ai/
2. Crie uma conta
3. Gere uma API key

### OpenWeather (Opcional - v4)

1. Acesse: https://openweathermap.org/api
2. Crie uma conta gratuita
3. Gere uma API key

---

## 🐛 Solução de Problemas

### Erro no PyAudio (Windows)

```bash
pip install pipwin
pipwin install pyaudio
```

### Erro no PyAudio (Linux)

```bash
sudo apt-get install portaudio19-dev python3-pyaudio
pip install pyaudio
```

### Erro no PyAudio (Mac)

```bash
brew install portaudio
pip install pyaudio
```

### Microfone não detectado

- Verifique permissões do sistema
- Teste com outro software de gravação
- Ajuste o `PAUSA_SILENCIO` no código

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para:

- Reportar bugs
- Sugerir novas funcionalidades
- Melhorar a documentação
- Criar novas tools para a v4

---

## 📄 Licença

Este projeto é para fins educacionais. Use livremente para aprender e criar seus próprios assistentes!

---

## 👨‍💻 Autor

- YouTube: [EAI Academy](https://www.youtube.com/@eaiacademy)
- GitHub: [eai-academy](https://github.com/eai-academy)
- Modificacoes e adaptacoes para Gemini : (https://github.com/CunhaRo)

