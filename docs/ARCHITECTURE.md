# Arquitetura

Registro e autorização → adaptadores CSV/JSON → normalização IBGE → deduplicação → rotas e oportunidades Python → JSON versionado → site e futuros consumidores.

O registro de descoberta não autoriza coleta. A esteira lê ofertas somente de manifestos explicitamente autorizados e valida prazo, SHA-256, escopo de publicação e domínio da oferta. Um arquivo que falha não bloqueia os outros. O estado e o cache ficam separados por modo: real local, real público, demonstração. Falha não renova a data da oferta nem a última observação. Não se carrega histórico de um feed fora do escopo atual. O build do Pages é por artefato fechado: nunca inclui arquivos brutos, manifestos ou cache.

O raio é em linha reta; a aproximação do centro municipal não é uma coordenada de terminal. Sem coordenadas, as ofertas permanecem no catálogo e podem aparecer na mesma cidade, mas não há distância estimada. Miritituba é um alias de Itaituba; a referência é o centro de Itaituba, não o acesso ao porto. Uma rota OSRM de carro não confirma restrições do rodotrem. Cache de 30 dias, direcional; acesso experimental, limitado, desativado na publicação agendada. © colaboradores [OpenStreetMap](https://www.openstreetmap.org/copyright) quando o roteador OSM for utilizado.

O ranking é calculado por hub. Proximidade, atualidade, compatibilidade, sinais de confiança, evidências e economia têm pesos explícitos. Sem base rodoviária não calculamos R$/km. A próxima carga é uma fotografia de ofertas recentes no entorno, não previsão de disponibilidade. O cliente só filtra a lista já ordenada.
