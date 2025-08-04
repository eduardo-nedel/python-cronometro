# Cronômetro

Cronômetro moderno em Python com PyQt6, modo compacto e atalho global.

## Requisitos
- Python 3.9+
- PyQt6
- keyboard (para atalho global)

## Instalação das dependências
```bash
pip install pyqt6 keyboard
```

## Execução
```bash
python cronometro.py
```

## Build executável (Windows)
```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed cronometro.py
```
O executável será gerado em `dist/cronometro.exe`.

## Atalho global
O atalho configurado funciona mesmo com a janela em segundo plano (requer permissão de administrador para capturar teclas globais no Windows).

## Modo compacto
Clique em "Modo Compacto" para exibir apenas o tempo e um botão discreto de restaurar.
