# Rastreador de Fretes Agro — protótipo independente

Busque por cidade onde o caminhão ficará vazio e raio de 0/50/100/150 km. O corredor de validação inicial é Primavera do Leste–Campo Verde–Rondonópolis, com catálogo de oito UFs e 16 hubs. Projeto independente; não usa contas, banco ou código do Minha Comissão.

```bash
python3 -m unittest discover -s tests -v
python3 -m pipeline.build --demo --refresh-ibge
python3 -m http.server 8219 --bind 127.0.0.1 --directory dist
```

Abra http://127.0.0.1:8219/. A demonstração não oferece fretes para contratação. Para entradas reais autorizadas, veja [Como fornecer cargas](COMO_FORNECER_CARGAS.md). O navegador não coleta dados de nenhuma plataforma; o diário experimental fica local e exporta métricas sem cadastro.

[Arquitetura](docs/ARCHITECTURE.md) · [Dados](docs/DATA_SCHEMA.md) · [Fontes](docs/SOURCES.md) · [Integração Flutter](docs/FLUTTER_INTEGRATION.md) · [Piloto](docs/PROTOTYPE_EVALUATION.md)
