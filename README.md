# Download automático de TikToks para anúncios no Meta

Roda todo dia sozinho no GitHub, sem instalar nada na sua máquina.
Lê a sua planilha do Google Sheets, baixa os vídeos novos e deixa um `.zip`
pronto para você baixar na aba **Actions**.

---

## Configuração (uns 15 minutos, uma vez só)

### 1. Publicar a planilha como CSV

**Arquivo → Compartilhar → Publicar na web → escolha a aba → Valores separados
por vírgula (.csv) → Publicar**

Copie a URL que aparecer. Ela termina em `output=csv`.

O script só lê as colunas B, C, E e F. Todo o resto ele ignora, então publicar
a aba inteira funciona sem problema.

**Aba espelho (opcional).** Publicar na web deixa o conteúdo acessível a quem
tiver o link, sem login. As colunas que o script usa são todas informação
pública, mas `Observações` pode acabar guardando nota interna que você não quer
exposta. Se preferir fechar isso, crie uma aba `Downloads` e coloque em **A1**:

```
={'NOME_DA_SUA_ABA'!B1:B, 'NOME_DA_SUA_ABA'!C1:C, 'NOME_DA_SUA_ABA'!E1:E, 'NOME_DA_SUA_ABA'!F1:F}
```

Troque `NOME_DA_SUA_ABA` pelo nome real da aba principal. Ela espelha só as
quatro colunas necessárias e se atualiza sozinha. Aí você publica essa aba em
vez da original.

### 2. Criar o repositório

1. No GitHub, crie um repositório **privado** (ex: `tiktok-downloads`)
2. Suba estes arquivos, mantendo a estrutura de pastas
3. Em **Settings → Actions → General → Workflow permissions**, marque
   **Read and write permissions** e salve

### 3. Cadastrar os secrets

Em **Settings → Secrets and variables → Actions → New repository secret**:

| Nome | Valor |
|---|---|
| `SHEET_CSV_URL` | a URL do passo 1 |
| `TIKTOK_COOKIES` | opcional, veja abaixo |

### 4. Colunas (já configurado)

O script já está apontado para os seus cabeçalhos:

| Papel | Coluna |
|---|---|
| Link do vídeo | `Link do vídeo (TikTok)` (B) |
| Nome do arquivo | `@TikTok` (C) + `Produto` (F) + `Cupom` (E) |

Os arquivos saem assim:

```
mariasilva__colageno_le_moritz__maria10__7391234567890123456.mp4
```

O handle identifica a criadora, o produto agrupa por campanha e o cupom liga o
criativo ao resultado de venda — dá pra achar qualquer coisa ordenando por nome.
Para mudar a ordem ou tirar um campo, edite `COLUNAS_NOME` no topo de
`scripts/baixar.py`.

A comparação de cabeçalhos ignora acentos, maiúsculas e pontuação, então se
alguém renomear a coluna para "Link do video TikTok" continua funcionando.

### 5. Rodar

Aba **Actions → Baixar TikToks → Run workflow**.

Quando terminar, o `.zip` com os vídeos aparece em **Artifacts**, no rodapé da
página da execução. A partir daí ele roda sozinho, dias úteis às 8h.

---

## Sobre confiabilidade

O GitHub Actions roda de um IP de datacenter, e o TikTok é mais rígido com
esses IPs do que com conexões residenciais. Na prática, você vai ver falhas
intermitentes em algumas linhas. O script foi feito para conviver com isso:

- Ele **não rebaixa** o que já veio (histórico em `baixados.txt`)
- Ele registra as falhas em `ultimo_relatorio.md`, commitado a cada execução
- Rodar o workflow de novo tenta apenas as linhas que faltaram

Se a taxa de falha ficar alta, o `TIKTOK_COOKIES` resolve na maioria dos casos.

### Como pegar os cookies

Instale a extensão **Get cookies.txt LOCALLY** (Chrome ou Firefox), abra o
TikTok logada, clique na extensão e exporte. Cole o conteúdo inteiro do arquivo
no secret `TIKTOK_COOKIES`.

Os cookies expiram de tempos em tempos — quando as falhas voltarem em massa,
é sinal de que precisa exportar de novo.

---

## Plano B

Se em algum momento a taxa de falha te incomodar mais do que gastar uns dólares,
o caminho é trocar o passo do download por um actor da **Apify**, que já vem com
proxy residencial. O resto da estrutura (planilha, agendamento, histórico)
continua igual — muda só a função `baixar_video()`.

---

## Custo

Zero, dentro dos limites gratuitos do GitHub: 2.000 minutos/mês de Actions em
repositório privado, e 500 MB de storage para os artifacts. Uma execução com
algumas dezenas de vídeos leva poucos minutos.
