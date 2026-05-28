$env:NANOCLICKER_VERSION = (git describe --tags --abbrev=0).TrimStart('v')
pyinstaller --onefile --windowed --name NanoAutoClicker --icon .\icon.ico --add-data ".\lang;lang" --clean .\main.py