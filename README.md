# Notepad Carrossel

Editor de notas em páginas, com cara de carrossel, feito em Python e PySide6. Os documentos ficam num banco SQLite ao lado do programa. A versão portátil para Windows não precisa de Python, de internet nem de instalação.

## Executar o código-fonte

É preciso Python 3.11 ou mais recente.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m notepad_carrossel
```

Os arquivos aparecem em `data\` e `backup\` na raiz do projeto, e não na pasta em que o terminal estava.

## Gerar a pasta portátil

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_portable.ps1
```

O script roda os testes, empacota com PyInstaller e monta:

```text
dist\NotepadCarrossel\
    NotepadCarrossel.exe
    data\
    backup\
    README.txt
```

Copie essa pasta inteira. Feche o programa antes, para a cópia levar a gravação mais recente. Não é preciso privilégio de administrador.

Se a pasta do executável não aceitar gravação, o programa avisa e pede outro lugar. A escolha fica registrada para a próxima abertura. Os documentos em si não vão para a pasta temporária do PyInstaller.

## Usar

Na abertura aparece a biblioteca de documentos. O mais recente fica selecionado; **Continuar** o reabre.

Cada página tem título, subtítulo, texto principal e, se quiser, blocos extras. A formatação de um bloco não altera os outros: alinhamento à esquerda, centralizado, à direita ou justificado, negrito, itálico, sublinhado, tamanho da fonte e listas.

As setas laterais trocam a página, com uma transição curta. O indicador mostra a posição, por exemplo `2 / 8`. Também dá para criar, duplicar, inserir antes ou depois e excluir com confirmação, além de ir à primeira e à última página.

As setas do teclado mudam de página quando o foco não está num campo de texto. Durante a digitação, a seleção e o movimento do cursor continuam normais; use **Alt + setas** para trocar de página sem sair do texto.

O canto superior mostra **Salvando**, **Salvo** ou **Erro ao salvar**. Não é obrigatório clicar em Salvar. Ctrl+S grava na hora.

## Backup e restauração

- **Arquivo → Backup agora** grava uma cópia em `backup\`.
- Há cópia automática periódica, ao fechar depois de editar e antes de excluir documento ou página.
- A cópia só é mantida se passar na verificação de integridade. Um arquivo corrompido não substitui uma cópia válida.
- **Arquivo → Restaurar backup** substitui o banco atual. Se ele ainda estiver íntegro, uma cópia de segurança é feita antes.
- Se o banco não abrir, o programa isola o arquivo em `backup\quarantine\` e oferece a cópia recente.

**Exportar** gera um `.notecarrossel.json` com páginas e formatação. **Importar** cria um documento novo e não apaga os existentes.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Eles cobrem documentos, formatação independente, navegação, salvamento automático, reabertura em outro processo, páginas, backup, caminhos com espaço e acento e, quando o executável já existe, a versão empacotada.
