# Descoberta de fontes — 23/11/2026

**Resultado:** encontramos uma fonte documental oficial e extraímos cinco lotes reais de transporte de milho em teste interno. Todos estavam encerrados. Não são cinco viagens disponíveis, nem cinco caminhões contratáveis. Nenhum dado do aviso foi integrado ao Pages.

## Universo e denominadores

O CKAN e o CSV mensal do [RNTRC](https://dados.antt.gov.br/dataset/rntrc) ficaram indisponíveis ou sem registros reconhecidos em execuções locais e do Actions. O extrator agora reconhece `cpfcnpjtransportador`, mantém somente CNPJ válido de ETC/CTC e preserva o último cache válido. Nenhuma contagem RNTRC foi inferida. O [painel TRC da ANTT](https://www.gov.br/antt/pt-br/assuntos/cargas/dadostrc) não foi tratado como arquivo de empresas.

Como universo alternativo, a planilha oficial [Operadores OEA ativos – Receita Federal](https://www.gov.br/receitafederal/pt-br/assuntos/aduana-e-comercio-exterior/importacao-e-exportacao/oea/operadores-ja-certificados-como-oea/operadores-OEA-ativos/view) forneceu **1.033 empresas brasileiras**, deduplicadas pela raiz do CNPJ. Priorizamos 500 por função certificada (transporte, carga, depósito ou operação portuária), indícios agro/logísticos no nome e exportação. A planilha não identifica RNTRC nem comprova oferta de carga.

Os sites vieram de um universo **separado**, sem presumir correspondência com essas 500 empresas: 328 vínculos comerciais explícitos nos diretórios da [ANATC](https://anatc.com.br/empresas-associadas/), [Abisolo](https://www.abisolo.com.br/associados/), [AMA Brasil](https://amabrasil.agr.br/Publicacao.aspx?id=396532), [ABIA](https://abia.org.br/a-abia/associadas/) e [ABIOVE](https://abiove.org.br/associados/). Após deduplicar e acrescentar o cadastro anterior, **330 domínios** receberam tentativa. **213** devolveram metadados úteis; **41** foram consultados sem metadados aproveitáveis, **71** indisponíveis e **5** adiados pela política de acesso. Contar 330 como 330 sites lidos com sucesso seria incorreto.

## Resultados da triagem

| Sinal | Resultado e interpretação |
|---|---|
| Sitemaps | 146 domínios com sitemap válido. |
| Páginas comerciais | 5 URLs candidatas em 4 domínios. Uma era promoção de varejo; as outras 4 pertencem a 3 transportadoras, sem listagem ingerível confirmada. |
| Plataformas | [Fribon](https://fribontransportes.com.br/fretes/) dirige ao app; [JCL](https://jcltransportes.com.br/fretes-disponiveis/) à Fretebras; [Botuverá](https://botuvera.com/agenciamento-de-cargas/) ao WhatsApp. Não usamos login, app, grupos ou mensagens. |
| Feeds | 71 indicações de URL; uma amostra por domínio com rota de feed, em 62 domínios. 60 eram RSS/Atom válidos, 1 não era feed e 1 não foi legível. Nenhum título na amostra continha os quatro sinais explícitos de disponibilidade testados. Isso não prova ausência de toda e qualquer oferta em seus históricos. |
| APIs e documentos | 5 URLs candidatas de documentação, das quais 4 eram na realidade PDFs sob uma pasta chamada docs. 21 outras URLs candidatas a documentos. Catálogo técnico anterior: 5 APIs documentadas, nenhuma bolsa pública de cargas confirmada. |
| Geo e sinais | 4 instalações institucionais já registradas; Overpass indisponível na rodada dos três hubs. Uma URL candidata a sinal operacional. Conversões geográficas em fonte de anúncio: zero. |

## Fonte documental validada

O índice oficial [Frete Autônomo da Conab](https://www.gov.br/conab/pt-br/atuacao/logistica/remocao-de-estoques/frete-autonomo) expõe avisos e resultados. O adaptador consultou robots, leu o aviso mais recente no índice, extraiu do PDF publicado o prazo de habilitação, o preço R$/t e as rotas por lote, e verificou a presença do resultado final. O aviso **006/2026** foi publicado em **19/10/2026**; o prazo era **29/10/2026 às 12h de Brasília**. Quantidades de edital não foram convertidas em viagens individuais; granel descreve a carga, não confirma carroceria nem rodotrem.

Cinco lotes distintos com preço; por origem: PR 1, MA 2, MS 2. Zero ativos e zero originados em MT. O teste mantém ID do documento+lote, primeira/última observação, publicação, validade e hash da fonte **no cache local**. Não redistribuímos o PDF ou uma versão transformada nem presumimos autorização de republicação por o portal ser público. A busca comercial não recebeu históricos nem propostas de licitação em substituição a fretes spot.

## Repetição e decisão

No repositório independente, executar `python -m pipeline.scale_sprint`, `python -m pipeline.feed_survey`, `python -m pipeline.conab_documents` e `python -m pipeline.scale_results` (Python com BeautifulSoup e xlrd; Poppler fornece pdftotext). O relatório agregado está em `data/scale_metrics.json`; registros operacionais e insumos ficam em `.cache/`. A descoberta corporativa e geográfica e a atualização de fretes mantêm cadências independentes na configuração existente. Uma nova execução massiva não deve ocorrer a cada busca do motorista.

As metas de tamanho foram alcançadas usando cadastro complementar, **não** com o RNTRC nem com vínculo individual entre cada empresa OEA e cada site. A escala revelou uma fonte de frete por lote e canais regionais reais, mas publicar fretes **atuais** exige uma janela aberta e direitos adequados. O melhor próximo teste é detectar a abertura de um novo aviso antes do prazo e ampliar transportadoras de granéis de MT com listagem própria, sem repetir em massa feeds institucionais genéricos.
