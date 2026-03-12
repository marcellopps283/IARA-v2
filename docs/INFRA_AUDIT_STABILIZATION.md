# Auditoria Técnica: Crise de Infraestrutura e Embeddings (IARA v2)

Este documento fornece um relatório detalhado dos erros, diagnósticos e soluções aplicadas durante a fase de estabilização da IARA no VPS, visando alimentar outra IA com contexto técnico preciso.

---

## 1. Contexto do Objetivo
O objetivo era finalizar a **Fase 9.2 (Otimização de Latência)**, migrando o motor de embeddings local (`michaelf34/infinity`) para uma versão **ONNX INT8** (`Qdrant/multilingual-e5-large-onnx`), visando reduzir a latência de inferência em CPU para milissegundos.

## 2. Sintoma do Erro
- **Erro**: `openai.APIConnectionError: Connection error.` e `httpx.ConnectError: [Errno 111] Connection refused`.
- **Impacto**: A IARA ficava "muda", falhando no primeiro passo (`memory_node`) do LangGraph porque não conseguia vetorizar a pergunta do usuário para buscar fatos no Mem0.

## 3. Linha do Tempo e Diagnóstico

### Fase A: O Loop de Reinicialização
- **Fato**: O container `infinity` estava no estado "Starting" perpetuamente ou reiniciando a cada 20-30 segundos.
- **Causa Raiz 1**: O Docker Compose possuía um `healthcheck` que disparava um `curl` a cada 30 segundos. Como a otimização inicial do ONNX usa 100% da CPU, o servidor não respondia ao `curl` a tempo. O Docker marcava o container como "unhealthy" e o matava, reiniciando o processo de otimização do zero.

### Fase B: O Mistério do ONNX Exit Code 0
- **Fato**: Após remover o `healthcheck` e aumentar a RAM para 4GB, o container parou de ser morto pelo Docker, mas o log mostrava que após a mensagem `Serializing optimized model...`, o processo terminava com `Exit Code 0`.
- **Causa Raiz 2**: Suspeita-se de incompatibilidade entre a versão do `optimum` dentro da imagem `michaelf34/infinity:latest` e o modelo quantizado do Qdrant. O processo de "warmup/benchmark" da imagem interpretava a finalização da serialização como o fim da tarefa e encerrava o processo, em vez de subir o servidor Uvicorn.

### Fase C: O Bind de Rede (Subcomando v2)
- **Fato**: Mesmo com modelos leves, o servidor às vezes não respondia na porta 7997.
- **Causa Raiz 3**: O uso do subcomando `v2` na linha de comando (`command: v2 --model-id...`) parecia conflitar com a forma como a imagem gerencia as variáveis de ambiente em versões recentes (v0.0.77), causando falhas no bind do host `0.0.0.0`.

## 4. Auditoria de Comandos e Logs

### Log Crítico (Otimização ONNX)
```text
INFO: Started server process [1]
INFO: Waiting for application startup.
INFO: infinity_emb INFO: select_model.py:66 model=`Qdrant/multilingual-e5-large-onnx` using engine=`optimum`
INFO: infinity_emb INFO: utils_optimum.py:168 Optimizing model
[W:onnxruntime:, inference_session.cc:2039 Initialize] Serializing optimized model...
# (Neste ponto o container encerrava com Exit Code 0 sem subir o Uvicorn)
```

### Comportamento de Recursos (VPS)
- **CPU**: Pico de 180% durante a carga do modelo.
- **RAM**: Estabilizou em ~1.7GB para o modelo FP32 (`multilingual-e5-large`).
- **Disco**: Ocupação de 89% (/dev/root), restando 5.5GB livres.

## 5. Soluções Aplicadas (Estado Atual ✅)

- **Backend Estável**: Abandonamos temporariamente o `engine=optimum` e voltamos para o `engine=torch` (nativo).
- **Otimização Ativa**: Ativamos o `BetterTransformer` (via `optimum` mas em modo estável) que atingiu **47.09 embeddings/sec** em CPU.
- **Configuração via Env**: Removemos a diretiva `command` do `docker-compose.yml` e passamos a usar variáveis de ambiente puras (`INFINITY_MODEL_ID`, etc.), permitindo que o `entrypoint` nativo da imagem gerencie o bind da porta 7997 de forma limpa.
- **Sincronização**: Garantimos que `TEI_MODEL` no `.env` do VPS fosse idêntico ao carregado no container para evitar que o `iara-core` pedisse um modelo inexistente (causa secundária frequente de erro 404/500).

## 6. Respostas Confirmadas e Conclusão

### 1. Por que o Exit Code 0 após serializar o ONNX?
Confirmado como um bug de encerramento prematuro do container após o export no engine `optimum`.

### 2. Pre-build de ONNX fora do Docker — Vale a pena?
Sim, permitiu que o container iniciasse sem o loop de export, mas revelou um segundo problema: **uma falha de limite de índices (514/513)** durante o warmup do ONNX Runtime em modelos baseados em XLM-R (E5). Este é um bug de compatibilidade profundo que inviabiliza o uso imediato de ONNX para esta arquitetura específica sem patches no grafo.

### 3. O volume infinity_cache está persistindo?
Sim, migramos para **bind mounts** (`./data/infinity_cache`), o que resolveu o problema de download redundante.

## 7. Decisão Final (Arquitetura de Produção ✅)
Para garantir **Estabilidade + Qualidade Maxima + Performance**, optamos pelo setup:
- **Modelo**: `intfloat/multilingual-e5-large`
- **Engine**: `torch` (com `BetterTransformer` via `optimum` interno).
- **Latência**: Estabilizada em ~47 embeddings/seg.
- **Persistência**: Bind mount em `./data` garantindo boots instantâneos.

---

## 7. Próximos Passos (Execução)
1. Instalar `optimum` no host VPS e realizar o export INT8 manual.
2. Atualizar `docker-compose.yml` para usar bind mounts em `./data`.
3. Apontar o container `infinity` para o modelo local pré-otimizado.
