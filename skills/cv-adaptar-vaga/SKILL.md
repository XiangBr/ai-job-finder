---
name: cv-adaptar-vaga
description: Adapta o CV base de um candidato a uma vaga específica (texto, link ou JSON do coletor), checando filtros, calculando aderência e reescrevendo com fórmula XYZ, storytelling e palavras-chave da vaga sem inventar nada. Use quando houver uma descrição de vaga e um CV/banco de fatos do candidato.
---

# Adaptar CV para uma vaga

Pré-requisitos, normalmente gerados pela skill `cv-diagnostico-e-perfil`:
- `fatos.yaml`: banco de fatos confirmados do candidato (fonte única de verdade)
- `cv_base.md`: versão base
- `filtros.yaml`: preferências e restrições de busca

Se faltar `fatos.yaml`, extrair os fatos do CV recebido antes de qualquer coisa (mesmo schema) e tratar tudo como `pendente` até o candidato confirmar.

## Regra zero: nada inventado

A adaptação muda **seleção, ordem, ênfase e vocabulário**. Nunca muda fatos.

Permitido:
- Escolher quais fatos entram e em que ordem.
- Usar o termo exato da vaga quando ele descreve a mesma coisa que o candidato fez ("painéis" → "dashboards"; "tratamento de dados" → "ETL" só se houve extração/transformação/carga de fato).
- Reescrever com mais clareza, resultado na frente, verbo mais preciso.
- Cortar o que não ajuda essa vaga.

Proibido:
- Adicionar ferramenta, tecnologia, certificação, número, escopo ou resultado que não está em `fatos.yaml`.
- Subir nível de proficiência (básico → intermediário).
- Transformar "participei" em "liderei", "apoiei" em "fui responsável".
- Copiar frases da vaga para dentro do CV como se fossem experiência.

Toda lacuna vira item na seção "Lacunas" do relatório, nunca texto no CV.

## Passo 1: Filtros eliminatórios

Antes de gastar esforço, conferir a vaga contra `filtros.yaml`:
- Modelo de trabalho e cidade (presencial/híbrido fora das cidades aceitas ou do raio → descartar)
- Nível (Pleno/Sênior quando o candidato busca estágio/júnior → descartar)
- Remuneração informada abaixo do mínimo → descartar; não informada → seguir e marcar
- Elegibilidade de estágio: disponibilidade exigida (ex.: "2 anos") maior que o tempo até a formatura → **bloqueio**; deixar a decisão para o candidato, explicando o conflito
- Trainee: janela de formatura exigida
- Inglês exigido acima do nível real → alerta
- Empresas bloqueadas, palavras excluídas

Saída: `APROVADA`, `APROVADA COM ALERTA (motivo)` ou `DESCARTADA (motivo)`. Se descartada, parar aqui e registrar o motivo em uma linha.

## Passo 2: Ler a vaga como o recrutador

Extrair para uma matriz:
1. **Problema do empregador:** em uma frase, o que essa pessoa vai resolver?
2. **Requisitos obrigatórios** e **desejáveis**, separados. Quando a vaga não separa, tratar como obrigatório o que aparece em "requisitos" e como desejável o que vem em "diferenciais", "vai se destacar", "plus".
3. **Palavras-chave exatas**, como escritas na vaga (PT e EN, siglas e nomes de ferramenta).
4. **Responsabilidades** traduzidas em competências (ex.: "levantamentos com áreas de negócio" → levantamento de requisitos, comunicação com stakeholders).
5. **Sinais de cultura e senioridade** (autonomia, ritmo, inglês, metodologias).

## Passo 3: Aderência

Para cada requisito, mapear IDs de fatos e classificar:
- **Forte:** fato confirmado mostra exatamente isso
- **Parcial:** fato próximo ou nível menor (ex.: SQL básico para "SQL intermediário")
- **Lacuna:** nada em `fatos.yaml`

Score (0 a 100):
- 60% obrigatórios: forte = 1, parcial = 0,5, lacuna = 0
- 25% responsabilidades com experiência equivalente
- 15% desejáveis

Decisão: ≥ 70 aplicar; 55 a 69 aplicar se houver bom argumento (registrar qual); < 55 não aplicar, salvo pedido do candidato. Qualquer bloqueio do Passo 1 aparece acima do score.

## Passo 4: Reescrever

Ordem de trabalho:
1. **Título-alvo:** espelhar o título da vaga se for verdadeiro para o candidato (ex.: "Estágio em Data Science & Analytics | Python · SQL · Power BI").
2. **Resumo (3 linhas):** identidade profissional + prova mais forte *para essa vaga* + conexão com o problema do empregador. Trocar o resumo é a mudança de maior efeito.
3. **Ordem das seções e experiências:** a experiência mais aderente sobe; projetos podem subir acima de experiências pouco relevantes.
4. **Seleção de bullets:** por experiência, os 2 a 5 fatos que cobrem requisitos. Fato que não cobre nada dessa vaga sai.
5. **Reescrita dos bullets** com as técnicas abaixo.
6. **Habilidades:** reordenar com as citadas na vaga primeiro, usando o nome exato da vaga. Retirar o que só polui.
7. **Corte:** caber em 1 página (2 no máximo).

### Técnicas de escrita

**Fórmula XYZ (Google):** "Alcançou X, medido por Y, fazendo Z". X é o resultado, Y é a prova (número, escala, frequência, escopo), Z é a ação e o método. O formato é um guia de conteúdo: a frase final não precisa ter "medido por".
- Fraco: "Responsável por dashboards de marketing."
- XYZ: "Dei visibilidade diária ao desempenho de campanhas para o time de Marketing (Y: 4 analistas, atualização automática) construindo dashboards em Power BI com modelagem e DAX (Z)."

**Escada de quantificação** (usar o degrau mais alto que for verdadeiro): valor exato > faixa > frequência > escopo (quem, quantos, qual área) > antes/depois qualitativo verificável.

**CAR / STAR para storytelling:** Contexto (ou Situação/Tarefa) → Ação → Resultado. No CV vira bullet compacto; na carta, mensagem ao recrutador e preparação de entrevista vira história de 4 a 6 frases.

**Fio narrativo:** antes de escrever, definir em uma frase por que essa pessoa resolve o problema desse empregador (ex.: "estudante de Matemática que já leva modelos e IA para dentro de uma gestora"). Resumo, ordem e bullets precisam contar essa mesma história.

**Front-loading:** resultado ou palavra-chave principal nas primeiras 8 a 10 palavras; recrutadores e ATS dão mais peso ao início da linha.

**Espelhamento de vocabulário com moderação:** usar o termo exato da vaga 1 a 2 vezes onde ele é verdadeiro, no resumo ou bullet mais forte e nas habilidades. Mirar em cobrir 60% a 80% dos obrigatórios verdadeiros. Cobertura máxima (repetir todas as keywords) reduziu entrevistas nos dados de 2 milhões de candidaturas.

**Verbos de ação em PT-BR:** desenvolvi, automatizei, construí, modelei, implementei, integrei, analisei, reduzi, padronizei, liderei (só se liderou), estruturei, validei, documentei, apresentei.

**Especificidade em vez de adjetivo:** trocar "forte capacidade analítica" por um fato que demonstra análise.

**Prova de IA:** se a vaga cita IA, subir o fato que mostra IA resolvendo um problema (o quê, como, resultado). Nunca listar ferramenta de IA que o candidato não usou.

**Padrões proibidos (anti-texto de IA):** travessão em excesso; "não é X, é Y"; dois-pontos armando revelação; adjetivos empilhados; "apaixonada por", "dinâmica", "proativa" sem fato; abrir resumo com "Profissional com sólida experiência". Ler em voz alta no fim.

## Passo 5: Checagem ATS e veracidade

1. **Tabela de veracidade:** cada bullet do CV adaptado → IDs de fatos. Bullet sem ID sai.
2. **Diff contra o CV base:** listar o que mudou (subiu, desceu, entrou, saiu, palavra trocada).
3. **Cobertura de palavras-chave:** obrigatórios cobertos / total; marcar se passar de ~85% (risco de stuffing) ou ficar abaixo de 50%.
4. **Formato:** coluna única, cabeçalhos padrão, sem tabelas/ícones, 1 a 2 páginas, nome do arquivo `Nome_Sobrenome_Cargo_Empresa.pdf`.

## Passo 6: Pacote de candidatura

Entregar:
1. `cv_<empresa>_<cargo>.md` (+ DOCX/PDF)
2. `relatorio_<empresa>.md` com: veredito do filtro, score e matriz de aderência, tabela de veracidade, diff, lacunas
3. **Lacunas e como tratar:** para cada lacuna, dizer se dá para cobrir com algo que o candidato já fez e não contou (gerar pergunta para ele), com um projeto pequeno, ou se é só aceitar
4. **Mensagem ao recrutador** (LinkedIn, até 300 caracteres), com um fato concreto
5. **3 perguntas prováveis de entrevista** com roteiro STAR montado só com fatos confirmados
6. **Respostas para formulário** (Gupy e similares) quando a vaga tiver perguntas
7. `vaga_resumo.json` para o agente de alertas:

```json
{"empresa": "", "cargo": "", "url": "", "veredito": "APROVADA|ALERTA|DESCARTADA",
 "motivo": "", "score": 0, "salario": "", "modelo": "", "lacunas": [], "arquivo_cv": ""}
```

## Contexto Brasil

- Vagas na Gupy usam o cadastro único do candidato; o CV adaptado serve para vagas com anexo (LinkedIn, e-mail, Greenhouse, Lever, sites próprios). Para a Gupy, a adaptação vale nas perguntas do formulário e na mensagem ao recrutador.
- Estágio: conferir carga horária (6 h/dia, 30 h/semana), duração exigida e previsão de formatura; no estágio não obrigatório, bolsa e auxílio-transporte são obrigatórios por lei.
- Títulos com flexão de gênero: no CV, usar a forma do candidato (Estagiária, Analista).
- Vaga em inglês: gerar o CV adaptado em inglês, com os mesmos fatos.
