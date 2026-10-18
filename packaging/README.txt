Notepad Carrossel
===================

Editor de notas em páginas, no estilo de um carrossel. Tudo fica neste
computador: não há login, não há servidor e não é preciso instalar Python.

Como abrir
----------
Dê dois cliques em NotepadCarrossel.exe.

Na primeira execução o programa cria as pastas data\ e backup\ ao lado do
executável. Os documentos ficam em data\notepad.sqlite. Você pode copiar a
pasta inteira para outro diretório, pendrive ou computador com Windows 10 ou 11.

Feche o programa antes de copiar a pasta, para que a cópia leve a versão
mais recente dos textos.

Não é necessário privilégio de administrador. Se a pasta do programa não
permitir gravação, o Notepad Carrossel pede outro local. Nesse caso os
documentos passam a ficar na pasta escolhida, dentro de data\ e backup\.

Uso
---
- Biblioteca: documentos recentes. "Continuar" abre o último selecionado.
- Cada documento tem várias páginas. As setas laterais trocam a página.
- Fora do texto, as setas do teclado também trocam a página.
- Durante a digitação, use Alt+seta esquerda e Alt+seta direita.
- O indicador mostra a posição, por exemplo 2 / 8.
- Cada bloco (título, subtítulo, texto e blocos extras) tem formatação
  própria: alinhamento, negrito, itálico, sublinhado, tamanho e listas.
- As alterações são salvas sozinhas. O canto superior mostra Salvando, Salvo
  ou Erro ao salvar. Ctrl+S salva na hora.

Backup
------
Menu Arquivo > Backup agora.

A cópia vai para a pasta backup\, com data e hora no nome. O programa também
cria cópias automáticas de tempos em tempos, ao fechar depois de editar e
antes de excluir um documento ou uma página.

Uma cópia só é gravada se o banco passar na verificação. Um arquivo
corrompido não substitui uma cópia boa.

Restaurar
---------
1. Feche outras janelas do Notepad Carrossel.
2. Menu Arquivo > Restaurar backup.
3. Escolha um arquivo .sqlite da pasta backup\.
4. Confirme. O estado atual, se ainda estiver íntegro, é copiado antes.

Se o banco não abrir, o programa avisa e oferece a cópia mais recente.
O arquivo danificado é movido para backup\quarantine\ e não é apagado.

Exportar e importar
-------------------
Arquivo > Exportar documento grava um arquivo .notecarrossel.json com as
páginas e a formatação. Arquivo > Importar documento cria um documento novo
a partir desse arquivo, sem substituir os que já existem.

Onde estão os arquivos
----------------------
NotepadCarrossel.exe
data\notepad.sqlite    documentos
data\app.log           erros de gravação, se houver
backup\                cópias de segurança
README.txt             este arquivo
