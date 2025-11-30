# Comparação entre API GraphQL vs API REST do GitHub

Este experimento busca-se compreender melhor o impacto do uso de APIs GraphQL, comparando esse modelo de API com o modelo mais comum REST. Para tal, foi escolhido a API do GitHub por sua popularidade, robusteza e por haver os dois tipos de API presentes na plataforma. Com isso em mente, foram propostas duas perguntas de pesquisa (research questions, RQs):

- RQ1. Respostas às consultas GraphQL são mais rápidas que respostas às consultas REST? 
- RQ2. Respostas às consultas GraphQL tem tamanho menor que respostas às consultas REST?

Em seguida, o desenho do experimento será descrito em tópicos

## Hipóteses

**RQ1 - Latência**

- H0 (nula): A latência média das consultas GraphQL é maior ou igual à latência média das consultas REST. (LatênciaMédiaGraphQL ​≥ LatênciaMédiaREST​)
- H1 (alternativa): A latência média das consultas GraphQL é menor que a latência média das consultas REST. (LatênciaMédiaGraphQL ​< LatênciaMédiaREST​)

**RQ2 - Tamanho**

- H0 (nula): O tamanho médio das respostas (especificar se comprimido/descomprimido) de GraphQL é maior ou igual ao tamanho médio das respostas REST. (TamanhoMédioGraphQL ​≥ TamanhoMédioREST​)
- H1 (alternativa): O tamanho médio das respostas de GraphQL é menor que o tamanho médio das respostas REST. (TamanhoMédioGraphQL ​< TamanhoMédioREST​)

## Variáveis

**Variáveis dependentes (VD)**

1. Latência total (ms) - tempo entre envio da requisição e recebimento do último byte da resposta (medido no cliente).
2. Tamanho da resposta (bytes, sem compressão) - tamanho do corpo JSON recebido.
3. Taxa de sucesso (%) - proporção de requisições com status 2xx por tratamento.
4. Número de chamadas REST necessárias - soma das chamadas REST necessárias para obter o mesmo conjunto lógico de dados.

**Variáveis independentes (VI)**

1. Tipo de API: {GraphQL, REST} - fator primário.
2. Complexidade da consulta: {Simples, Média, Complexa} - definida operacionalmente abaixo.
3. Autenticação: uso de token (constante para todas as requisições).
4. Ordem de execução: aleatorizada entre repetições para prevenir efeitos de ordem.

## Tratamentos (combinações de fatores)

Cada tratamento é a combinação dos níveis dos fatores: API × Complexidade.

**Níveis definidos:**

- API: GraphQL, REST (2 níveis).

**Complexidade:**

- Simples: recurso único com 1–3 campos (ex.: informações básicas de usuário).
- Média: recurso com 6–10 campos ou lista curta (ex.: metadados de repositório).
- Complexa: consulta aninhada e/ou que exige paginação (ex.: últimos 50 issues com autor e labels).

Total de tratamentos: 2 × 3 = 6.

A unidade de comparação é a tarefa lógica (mesmo conteúdo desejado). Para REST, quando necessário, somar as latências de todas as chamadas REST da tarefa lógica antes de comparar com a chamada GraphQL.

## Objetos experimentais

Serão utilizados múltiplos objetos por categoria para permitir generalização.

**Categorias e seleção:**

1. Usuário (simples): 5 usuários distintos (mistura de perfis populares e pouco ativos). Campos: login, id, name, followers_count.
2. Repositório (média): 5 repositórios (3 populares, 2 pequenos). Campos: name, owner, description, stargazers_count, forks_count, license.
3. Issues / Commits (complexa): 5 repositórios (podendo haver sobreposição com a categoria repositório) para extração de listas:
    - Issues: últimos 50 issues (título, número, author login, labels).
    - Commits: últimos 10 commits (sha, message, author login, date).

Para cada objeto será definida uma query GraphQL e o conjunto de chamadas REST que devolve dados logicamente equivalentes. O mapeamento campo a campo será documentado.

## Tipo de projeto experimental

Within-subjects (pareado): cada tarefa lógica será executada em ambos os níveis do fator API (GraphQL e REST), gerando pares de observações. A ordem das execuções em cada par será aleatorizada. Uma seed fixa será usada para reprodutibilidade.

## Quantidade de medições e parâmetros operacionais

**Parâmetros escolhidos:**

- **Replicações por combinação (por objeto):** 50 repetições.
- **Objetos por categoria:** 5.
- **Número total de requisições estimadas:** 2 APIs × 3 complexidades × 5 objetos × 50 repetições = 1.500 requisições.
- **Warm-up:** 10 execuções iniciais descartadas por combinação.
- **Intervalo entre requisições:** intervalo aleatório entre 100 ms e 300 ms.
- **Timeout por requisição:** 30 s. Requisições que excederem timeout serão registradas como falha.
- **Retries:** 1 retry com backoff exponencial em falha de rede; re-tentativas serão marcadas no log.
- **Cabeçalhos de compressão:** nenhum cabeçalho Accept-Encoding será enviado — assim, todas as respostas chegam sem compressão do lado do servidor.
- **Justificativa:** 50 repetições por condição fornecem robustez estatística frente à variabilidade de rede e permitem aplicar testes pareados.

## Ameaças à validade e medidas mitigadoras

1. Construto

- **Ameaça:** ambiguidade sobre o que significa "tamanho da resposta".
- **Mitigação:** definir explicitamente que o tamanho medido é o tamanho do corpo JSON recebido sem compressão, já que não será usado Accept-Encoding.

2. Interna

- **Ameaças:** caching (CDN), variação de rede do cliente, rate-limits do GitHub.
- **Mitigações:** enviar Cache-Control: no-cache / Pragma: no-cache quando aplicável; usar autenticação por token; monitorar cabeçalhos X-RateLimit-* e registrar eventos de limitação; aleatorizar ordem de execução; descartar warm-ups.

3. Externa

- **Ameaça:** seleção dos objetos pode limitar generalização.
- **Mitigação:** escolher objetos variados (populares e pequenos) e descrever critérios de seleção no relatório.

4. Estatística (conclusão)

- **Ameaças:** violação de pressupostos (normalidade) e múltiplas comparações.
- **Mitigações:** testar normalidade das diferenças (Shapiro-Wilk); usar paired one-tailed t-test se normalidade for plausível, senão Wilcoxon signed-rank one-tailed; ajustar p-valores com método Holm quando houver múltiplas subcomparações; reportar medianas e IQR além de médias e desvio.

5. Operacional

- **Ameaças:** instrumentação incorreta (medição de tempo/tamanho).
- **Mitigações:** validar o script de medição contra servidor de teste local; medir timestamps com relógio monotônico; confirmar contagem de bytes lidos do corpo quando Content-Length ausente.