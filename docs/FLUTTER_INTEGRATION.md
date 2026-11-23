# Integração futura — Autônomo → Buscar Fretes

A futura tela recebe código IBGE da cidade onde o caminhão ficará vazio, carrega `meta.json`, `cargas.json` e `oportunidades/{ibge}.json` e confere a versão e o snapshot em comum. Usa a ordem, distâncias, selos e métricas já calculados em Python; aplica filtros de apresentação e abre a oferta original. Tratar null, timeouts, cidade sem hub e snapshot expirado; cache com expiração e identidade de snapshot. O próximo passo pode substituir a leitura estática por API sem alterar o modelo de oportunidade.

O destino da viagem atual pode preencher o município, sem transmitir dados da conta ao catálogo. Um futuro botão **Usar como nova viagem** cria um rascunho revisável com origem, destino, produto e valor/distância se conhecidos. Não cria pagamento, compromisso nem lançamento automaticamente. Rentabilidade/diesel e perfil de veículo podem ser parâmetros em versão futura; não duplicar regras no Flutter. Nada foi instalado no app atual.
