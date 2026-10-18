# Relatório — Notepad Carrossel 1.0.0

Aplicativo desktop portátil para Windows, em Python e PySide6, com documentos em páginas e banco SQLite ao lado do executável. Não há login, API externa nem necessidade de Python na máquina de destino.

## O que foi implementado

- Editor por blocos. Cada página tem título, subtítulo e texto principal, e pode receber blocos extras. Alinhamento, negrito, itálico, sublinhado, tamanho da fonte e listas ficam no bloco em que foram aplicados.
- Carrossel de uma página por vez, com setas laterais, indicador `2 / 8`, transição em esmaecimento, primeira e última página, nova página, duplicar, inserir antes ou depois e excluir com confirmação.
- Setas simples do teclado trocam de página quando o foco não está num campo de texto. Dentro do editor, elas movem o cursor; Shift continua a seleção. Alt + setas troca de página durante a digitação.
- Salvamento automático, salvamento manual e indicador Salvando, Salvo ou Erro ao salvar. SQLite em transações, com WAL quando o disco permite e journal comum como alternativa.
- Biblioteca de documentos na abertura, com o mais recente selecionado. Criar, abrir, renomear e excluir (com confirmação e cópia de segurança antes).
- Pasta portátil calculada pela localização do executável, não pelo diretório de trabalho e não pela pasta temporária do PyInstaller. Se essa pasta não puder ser gravada, o programa avisa e pede outro local.
- Backup manual, automático e antes de exclusões. Restauração só aceita cópia íntegra. Exportação e importação em JSON preservam páginas e formatação.
- Empacotamento com PyInstaller em um único executável de janela, com o interpretador e as bibliotecas incluídos.

## Pasta portátil

```text
dist\NotepadCarrossel\
    NotepadCarrossel.exe    48.317.968 bytes
    data\notepad.sqlite     banco local, sem documentos de teste
    backup\
    README.txt
```

Para usar, copie a pasta inteira e abra `NotepadCarrossel.exe`. Não é preciso administrador nem internet.

## O que foi testado

Suíte automatizada, em 18/10/2026, com a tela fora da área visível (`QT_QPA_PLATFORM=offscreen`):

```text
35 passed
```

Cobertura:

1. Criação, edição, reabertura e rejeição de nome vazio.
2. Formatação independente dos blocos, inclusive listas que não vazam para o bloco vizinho.
3. Setas da interface e do teclado, sem roubar cursor nem seleção dentro do editor.
4. Salvamento automático e indicador de erro ao gravar.
5. Fechar e abrir de novo, inclusive em outro processo, sem perder texto nem formatação.
6. Criar, duplicar, ordenar e excluir páginas, com confirmação na exclusão.
7. Backup, recusa de cópia corrompida e exportação/importação.
8. Caminho com espaços e acentos, e recusa de gravar dados na pasta temporária do PyInstaller.

O executável empacotado foi executado com o `PATH` limitado a `C:\Windows\System32` e sem `PYTHONPATH` nem `PYTHONHOME`:

- `--smoke-gui` terminou com código 0 e abriu a janela.
- `--self-test` na própria pasta portátil terminou com código 0 (`SELFTEST_OK`). O banco ficou em `dist\NotepadCarrossel\data\notepad.sqlite`, com as tabelas `documents`, `pages`, `blocks` e `app_state`, e zero documentos restantes.
- `--self-test --root` em `dist\área de trabalho\Notepad Carrossel` também terminou com código 0. Essa pasta de prova foi removida depois.
- O teste `test_packaged_executable_roundtrip` repetiu o autoteste do `.exe` num diretório temporário com espaço e acento.

Nada foi enviado ao Git.
