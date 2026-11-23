# Contratos 1

`cargas.json`, `meta.json`, `sources_registry.json` e `oportunidades/{ibge}.json` têm `schema_version` inteiro e `snapshot_id` comum. `modo` é DEMO ou REAL. Não misturar snapshots ou modos. Campos adicionais podem ser ignorados; uma mudança incompatível exige outra versão. Links e descrições externas são dados, nunca HTML.

- Carga: ID opaco, municípios IBGE/UF, peso em t, valor original e unidade; dinheiro normalizado em centavos inteiros BRL. Ausente = null, não zero. Um preço por t só gera referência 50 t se o peso anunciado não contradiz; valor fechado nunca é reescalado. A referência não considera custos. Os campos privados de agrupamento não são exportados.
- Disponibilidade: `publicado_em`, `validade`, `primeira_vez_vista`, `ultima_vez_vista` e evidência por fonte. Relógios ISO 8601 UTC, apresentados em Cuiabá. Expiração declarada vence heurística de idade: até 12 h Nova, até 36 h Recente, até 72 h Antiga, acima disso Possivelmente expirada. Nenhum selo implica que a carga ainda esteja disponível.
- Deduplicação: mesma origem do registro por ID de fonte; entre fontes exige empresa e referência comum do embarcador, rota, produto, configuração, peso e janela de 48 h. Pode deixar anúncios sem referência separados; não junta só por preço ou rota. Reconciliação conserva histórico de valores e ID em builds com o mesmo cache.
- Oportunidade: `carga_id`, raio geográfico, pernas e método, total, métricas econômicas opcionais, sinais do posicionamento e contagem de ofertas próximas ao destino. Um método aproximado ou desconhecido não vira R$/km rodoviário.
- Fonte: classe, origem da evidência, saúde, contagens e datas. O catálogo não comprova cobertura de ofertas reais em cada estado.
