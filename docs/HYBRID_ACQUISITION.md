# Aquisição híbrida

O catálogo próprio continua independente. A lista pública contém **somente demonstrações sintéticas**. A captura privada e a pesquisa federada já são úteis com zero feeds reais. Os modos não equivalem a permissões.

| Modo | Fluxo atual |
| --- | --- |
| USER_CAPTURE | Colar, interpretar, revisar, calcular e descartar em memória. Sem analytics, cookies, telemetria própria, envio, contribuição coletiva ou histórico de oferta. |
| FEDERATED_SEARCH | Links oficiais. Fretebras e Puxada têm páginas verificadas para Rondonópolis; as demais combinações usam entrada oficial sem inventar parâmetros. O link Puxada é regional, não filtro exato de saída. |
| OPEN_INGEST | Zero fontes de oferta com direitos verificados. Não há download automático de anúncios; a esteira de arquivos CSV/JSON e normalização está pronta. |
| PUBLISHER_INPUT | Recebimento voluntário de CSV/JSON sob autorização verificável; XLSX exportado para CSV. E-mail, planilha e bot/webhook futuros são canais de entrega autorizada, não coleta de conta/grupo. |
| CONTEXT_SOURCE | SIFRECA, ANTAQ, Conab e ANEC. Referências, não cargas. |
| RESTRICTED_SOURCE | Sem coleta de Vector, WebFrete, Telegram/grupos, páginas autenticadas ou endpoints privados. Fretebras e Puxada só são oferecidas para navegação externa. |
| OFFICIAL_VALIDATION | IBGE para municípios; Receita e ANTT para confirmação humana. |

## Descoberta e autorização

- [Fretebras, termos 1.11 e 5.11](https://www.fretebras.com.br/termos-de-uso): `LINK_ONLY`. [Entrada oficial de Rondonópolis](https://www.fretebras.com.br/fretes/carga-de-rondonopolis-mt/com-valor).
- [Puxada, termos](https://www.puxada.com.br/termos) e [página municipal](https://www.puxada.com.br/fretes/em/mt/rondonopolis): acesso via link; nenhum direito de ingestão ou redistribuição confirmado.
- [Rodolívia](https://rodoliviatransportes.com.br/) divulga fretes e operações de grãos; candidata a CSV voluntário. [Indiana](https://indianatransportes.com.br/app/manual/manual_usuario.pdf) documenta conta aprovada no app; não usar. [Cargas.com.br](https://cargas.com.br/para-transportadoras) documenta cadastro/créditos; não usar. [1500](https://www.1500transportes.com.br/ondeestamos), [CS Transportes](https://cstransportesgraos.com.br/) e cooperativas/tradings no catálogo seguem em descoberta.
- [Dados abertos ANTT](https://dados.antt.gov.br/dataset/transporte-rodoviario-de-cargas) e [plano de dados ANTAQ](https://www.gov.br/antaq/pt-br/acesso-a-informacao/dados-abertos/plano-de-dados-abertos): informações setoriais, não ofertas individuais abertas.
- Provar titularidade, direito de acesso automatizado, republicação, escopo, prazo, origem e retirada. Verificar termos, licença e robots para **a URL exata do feed**, e documentar evidências; robots por si só não autoriza. Primeiro validar esquema, atualidade, compatibilidade e origem em modo não público. Para publicação real, revisar a [Lei 15.485/2026, art. 5º-F](https://anttlegis.antt.gov.br/action/ActionDatalegis.php?acao=abrirTextoAto&cod_menu=7145&cod_modulo=420&nomeTitulo=codigos&numeroAto=00015485&orgao=NI&seqAto=000&tipo=LEI&valorAno=2026). O build público real exige autorização, revisão explícita, preço total verificável e piso em centavos para a operação, sem substituir revisão regulatória. O workflow do Pages está fixado em `--demo --public`.

## Análise e contexto

- O parser determinístico opera com o fuso de Cuiabá e catálogo do IBGE nos oito estados piloto. UF e contexto explícitos ajudam a resolver municípios. Valores ambíguos, como “frete 470” ou “470 ton” fora do intervalo de peso, não assumem R$/t. Validação sintática de CNPJ não é consulta cadastral. Motor comum em Python, com runtime WebAssembly verificado, carregado apenas quando o usuário interpreta uma oferta.
- [SIFRECA/ESALQ](https://sifreca.esalq.usp.br/sifreca): link oficial e inserção local de referência consultada pelo usuário; sem licença confirmada para coleta, cache de dados da fonte ou republicação. A comparação exige a mesma rota, produto, unidade e referência datada até 30 dias. Não garante disponibilidade.
- [Calculadora oficial ANTT](https://calculadorafrete.antt.gov.br/): comparação opcional com resultado em reais para a mesma operação, somente após conferir distância rodoviária e parâmetros. Não declara ilegalidade automaticamente. R$/km não é calculado usando linha reta.
- [Anuário ANTAQ 2025](https://www.gov.br/antaq/pt-br/central-de-conteudos/publicacoes-da-antaq/Anuario2025.pdf), [Conab](https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/safras/safra-de-graos), [ANEC](https://anec.com.br/estatisticas/): contexto histórico de escoamento e safra. Sem alteração no ranking por falta de dados comparáveis por oferta.
- Posição explicada por proximidade, atualidade, compatibilidade, economia quando calculável, confiança, corroboração e até 6 pontos por sinais de próximo frete no snapshot. A deduplicação prioriza referência comum, não preço/contato isolado; preserva fontes, evidências e histórico. A captura privada nunca é usada na deduplicação pública.

## Como verificar

`python3 -m unittest discover -s tests -v` e `python3 -m pipeline.build --demo --public --refresh-ibge --browser-runtime`. No Chromium, colar o exemplo fictício Primavera do Leste/MT → Santos/SP, soja, rodotrem graneleiro, 50 t, R$ 470/t. Conferir R$ 23.500, distância rodoviária ausente e ausência de R$/km até informar km. Testar segundo cálculo offline, botão de limpeza, recarga, links oficiais e rede sem conteúdo da captura.
