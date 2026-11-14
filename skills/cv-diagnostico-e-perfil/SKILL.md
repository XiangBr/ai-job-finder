---
name: cv-diagnostico-e-perfil
description: Analisa o currículo de um candidato (contexto Brasil), entrevista para extrair métricas reais, gera uma versão base otimizada para ATS e parametriza os filtros de busca de vagas. Use quando alguém enviar um CV para revisar, melhorar, deixar "ATS-friendly" ou configurar alertas de vaga.
---

# CV: diagnóstico, entrevista e perfil de busca

Fluxo em 5 fases. Cada fase entrega um artefato que alimenta a próxima e também a skill `cv-adaptar-vaga`.
Não pule a Fase 2. Reescrever um CV sem números verdadeiros só troca palavras.

## Princípios inegociáveis

1. **Nada inventado.** Todo número, ferramenta, cargo, data ou resultado vem do CV original ou de uma resposta explícita do candidato. Sem número disponível, use escopo, frequência ou volume que o candidato confirmar. Estimativa só com "~" e só se o candidato aceitar.
2. **Banco de fatos antes do texto.** Primeiro extraia fatos para `fatos.yaml`; depois escreva. Cada bullet final aponta para IDs de fatos.
3. **Defensável em entrevista.** Se o candidato não consegue explicar uma linha em 30 segundos, ela sai.
4. **Dois leitores.** Primeiro a máquina (ATS/IA ranqueia), depois a pessoa (decide). Formato simples para a máquina, conteúdo específico para a pessoa.
5. **Escrita humana.** Evitar: travessão em excesso, "não é X, é Y", dois-pontos armando revelação, adjetivos empilhados, chavões ("profissional dinâmica, proativa e apaixonada por desafios"), abertura genérica ("num mundo cada vez mais...").

Base de evidências (use para justificar recomendações ao candidato):
- Em quase 2 milhões de candidaturas, CVs adaptados à vaga tiveram 5,71% de taxa de entrevista contra 3,09% dos genéricos; os CVs com maior cobertura de palavras-chave tiveram 21% menos entrevistas que os de cobertura moderada (guia de Jeff Su, set/2026). Adaptar sim, entupir de keyword não.
- CVs com impacto quantificado tiveram 75% mais entrevistas que os que só descrevem responsabilidades (mesmo guia).
- 87% dos gestores dizem que o software de triagem lê melhor CVs simples, em texto, do que visuais.
- Mostrar uso real de IA num problema relevante aumenta a chance de entrevista; listar "ChatGPT" em skills não basta.

## Fase 0: Ingestão

1. Ler o arquivo (PDF, DOCX ou texto colado). Em PDF, conferir se o texto é selecionável. Extração vazia ou embaralhada já é o achado nº 1 de ATS.
2. Extrair tudo para `fatos.yaml` no schema abaixo. Copiar o texto original de cada item; não melhorar nada ainda.
3. Marcar `status: pendente` em tudo que precisa de confirmação ou número.

```yaml
candidato:
  nome: ""
  cidade_uf: ""
  contatos: {email: "", telefone: "", linkedin: "", github: "", portfolio: ""}
  formacao_atual: {curso: "", instituicao: "", inicio: "AAAA", previsao_conclusao: "AAAA-MM", semestre_atual: null}
experiencias:
  - id: EXP1
    empresa: ""
    cargo: ""
    area: ""
    tipo: estagio | clt | pj | aprendiz | summer | trainee | freelance | voluntario
    inicio: "AAAA-MM"
    fim: "AAAA-MM | atual"
    fatos:
      - id: EXP1.F1
        texto: "o que fez, em palavras simples"
        ferramentas: []
        metrica: null      # {valor, unidade, tipo: exata|faixa|frequencia|escopo, fonte: cv|entrevista}
        resultado: null    # o que mudou por causa disso
        status: confirmado | pendente
projetos:            # IC, extensão, empresa júnior, projetos pessoais, hackathons
  - id: PRJ1
    nome: ""
    papel: ""
    inicio: ""
    fim: ""
    fatos: []        # mesmo formato de experiencias.fatos
certificacoes:
  - {id: CER1, nome: "", emissor: "", ano: "", area: "", relevante_para: []}
skills:
  - {nome: "Python", nivel_declarado: "", evidencias: ["EXP1.F2"]}
idiomas:
  - {idioma: "", nivel: "", cefr: ""}
premios: []
```

## Fase 1: Diagnóstico

Avaliar 9 dimensões (nota 0 a 3). Entregar `diagnostico.md` com: tabela (dimensão, nota, achado, correção), as 5 correções de maior impacto em ordem, e o que já está forte (para não estragar).

| # | Dimensão | O que checar |
|---|---|---|
| 1 | Leitura por máquina | Coluna única; sem tabelas, caixas de texto, ícones, barras de skill, imagens ou cabeçalho/rodapé com dados; cabeçalhos padrão; texto selecionável; PDF < 2,5 MB ou DOCX; fonte padrão 10 a 12 |
| 2 | Posicionamento | Em 6 segundos dá para saber o cargo-alvo? Tem título-alvo no topo? O resumo é específico ou serve para qualquer pessoa? |
| 3 | Impacto | % de bullets com resultado ou escala mensurável. Parágrafo corrido de responsabilidades = nota 0 |
| 4 | Relevância e poda | O que não ajuda o cargo-alvo dilui o resto: cursos antigos de outra área, listas longas de certificações, tarefas genéricas |
| 5 | Palavras-chave | Termos que vagas do cargo-alvo pedem e que o candidato tem mas não escreveu (ex.: escreveu "relatórios", a vaga pede "dashboards"; usa SQL mas não citou) |
| 6 | Prova de IA | Lista ferramenta (fraco) ou descreve problema resolvido com IA e resultado (forte)? |
| 7 | Coerência | Datas no mesmo formato, sem lacunas sem explicação, nomes de empresa e acentos corretos, ortografia |
| 8 | Tamanho e ordem | Até ~3 anos de experiência: 1 página ideal, 2 no máximo. Experiência antes de formação, salvo se a experiência for irrelevante para o alvo |
| 9 | Contexto Brasil | Ver seção "Contexto Brasil" |

Sinais de alerta comuns:
- Nível "básico" autodeclarado em ferramenta central da vaga-alvo (Excel/SQL para BI). Perguntar o uso real antes de decidir manter, retirar o nível ou trocar por evidência.
- Mesma empresa com cargos sucessivos listados como blocos soltos. Agrupar mostra progressão (ex.: summer job → estágio).
- Skills listadas sem evidência em nenhuma experiência ou projeto.

## Fase 2: Entrevista de métricas

Objetivo: transformar cada fato `pendente` em fato com métrica ou escopo confirmado.

Condução:
- Uma experiência por vez, começando pela mais relevante para o cargo-alvo.
- No máximo 3 perguntas por mensagem, concretas, com exemplo de resposta possível.
- Quando a pessoa disser "não sei o número", descer a escada de quantificação: valor exato → faixa ("entre 5 e 10") → frequência ("toda semana") → escopo ("para a diretoria de marketing, 6 pessoas") → antes/depois verificável ("passou a ser automático").
- Perguntas-chave que destravam métrica: Como era feito antes de você? Quanto tempo levava? Quem usava o resultado e com que frequência? Que decisão foi tomada com base nisso? O que daria errado se você não fizesse?
- Registrar cada resposta em `fatos.yaml` com `fonte: entrevista`.
- Se o candidato não estiver presente (outra pessoa enviou o CV), gerar `perguntas_entrevista.md` agrupado por experiência e deixar placeholders `[[...]]` no CV base.

Banco de perguntas por tipo de experiência:
- **Dashboards / BI:** Quantos dashboards ou relatórios? Quais KPIs? Quantas pessoas ou áreas usam? Atualização manual ou automática, com que frequência? Quantas fontes de dados integra? Que decisão ele apoia?
- **Automação (Python, RPA, scripts):** Que tarefa foi automatizada? Tempo antes e depois? Frequência da tarefa? Quantas pessoas deixaram de fazer à mão? Erros evitados?
- **Modelagem / ML / IA generativa:** Qual problema de negócio? Que dados (volume, período)? Métrica técnica (erro, acurácia) e métrica de negócio? Foi usado de verdade? Por quem? No caso de LLM: que tarefa o modelo faz, quantos casos processa, quanto tempo de análise economiza, como a saída é validada?
- **Pesquisa / iniciação científica:** Pergunta de pesquisa? Volume e período dos dados? Métodos e linguagem? Achado principal? Apresentação, publicação, prêmio?
- **Liderança / extracurricular:** Tamanho da equipe? Meta? Resultado na competição ou entrega? Que decisão técnica foi sua?
- **Administrativo / operações / faturamento:** Volume (notas por mês, itens, documentos)? Prazos? Erros ou retrabalho reduzidos? Manuais criados e quem usa?
- **Atendimento / vendas:** Volume, metas, conversão, NPS, tempo de resposta.

## Fase 3: CV base

Uma versão base, otimizada para o cargo-alvo principal, que a skill `cv-adaptar-vaga` vai ajustar por vaga.

Estrutura (cabeçalhos em PT-BR, nesta ordem):
1. **Nome** e linha de contato: Cidade - UF | telefone | e-mail | LinkedIn | GitHub/portfólio (se houver)
2. **Título-alvo** em uma linha: cargo + 3 a 4 competências centrais (ex.: "Estágio em Ciência de Dados | Python · SQL · Power BI")
3. **Resumo** (até 3 linhas): quem é + prova mais forte + direção. Sem adjetivos de personalidade.
4. **Experiência profissional** (reverso-cronológica). Cargos sucessivos na mesma empresa ficam sob a empresa. 2 a 5 bullets por cargo, o mais relevante primeiro.
5. **Formação**: curso, instituição, início e previsão de conclusão (obrigatório para estágio e trainee).
6. **Projetos e pesquisa**: só os que reforçam o cargo-alvo.
7. **Habilidades** agrupadas (ex.: Dados e programação / BI e visualização / IA / Cloud e ferramentas). Sem barras, estrelas ou porcentagens.
8. **Certificações**: só as relevantes; agrupar o restante numa linha ou cortar.
9. **Idiomas** com nível (CEFR se souber).

Regras de bullet:
- Fórmula XYZ do Google adaptada: "Alcançou X, medido por Y, fazendo Z". Na prática: verbo de ação + resultado/escala + como. Não precisa usar literalmente "medido por".
- Verbo no passado; cargo atual pode usar presente.
- Resultado ou escala nos primeiros 8 a 10 palavras sempre que existir.
- 1 a 2 linhas. Sem primeira pessoa ("eu").
- Sem métrica confirmada: escopo + ação + finalidade ("Construo dashboards de Power BI com modelagem e DAX para o time de Marketing").

Exemplos (antes → depois):
- "Responsável por relatórios semanais" → "Automatizei em Python o relatório semanal de campanhas, reduzindo a preparação de ~3 h para 15 min" (só se os números foram confirmados).
- "Participei de projetos de IA" → "Integrei o ChatGPT a uma automação que interpreta regras de enquadramento regulatório de fundos" (fato do CV, sem número inventado).

Saídas:
- `cv_base.md`
- DOCX e PDF de coluna única (Calibri ou Arial 10,5 a 11; margens ~2 cm; PDF com texto selecionável). Nome do arquivo: `Nome_Sobrenome_Cargo.pdf`.
- `mapa_fatos.md`: cada bullet → IDs de fatos de onde saiu.
- Headline sugerida para o LinkedIn e campos para revisar na Gupy.

Checagem final antes de entregar:
1. Todo bullet tem ID de fato? Algum número não veio do candidato? (se sim, remover)
2. Ler em voz alta: soa como a pessoa ou como um gerador de texto?
3. Passar a lista de padrões do princípio 5.
4. Cabe em 1 página (2 no máximo)?

## Fase 4: Entrevista de filtros de vaga

Perguntar em blocos de até 4 perguntas, com opções clicáveis quando a interface permitir. Preencher o que já foi dito e só perguntar o que falta. Produzir `filtros.yaml`:

```yaml
perfil_busca:
  cargos:                       # em ordem de prioridade
    - {area: "Ciência de Dados", prioridade: 1,
       titulos: ["Cientista de Dados", "Data Scientist", "Estágio em Ciência de Dados", "Data Science"],
       excluir_titulos: ["Pleno", "Sênior", "Sr", "Lead"]}
  nivel: [estagio, trainee, junior, analista]
  contrato: [estagio, clt, pj]
  modelo_trabalho:
    remoto: {aceita: true, prioridade: 1, abrangencia: "Brasil"}
    hibrido: {aceita: true, prioridade: 2, cidades: ["Curitiba - PR"]}
    presencial: {aceita: true, prioridade: 3, cidades: ["Curitiba - PR"]}
  raio_km: 30
  aceita_mudanca: false
  remuneracao:
    estagio: {minimo_bolsa: 0, alvo: 0}
    clt: {minimo_base: 0, alvo: 0, exige: ["VR", "VT"]}
    nao_informado: marcar       # marcar | descartar
  beneficios_desejaveis: []
  empresas_alvo: []             # nome + slug Gupy/Greenhouse/Lever/LinkedIn company id quando possível
  empresas_bloqueadas: []       # inclui empregador atual se a busca for sigilosa
  setores_preferidos: []
  setores_evitar: []
  idiomas_vaga: [pt, en]
  ingles_maximo_exigido: ""     # ex.: "intermediário"; acima disso, marcar como alerta
  restricoes_eliminatorias:
    disponibilidade_estagio_max_meses: null   # calcular a partir da previsão de formatura
    anos_experiencia_max: null
    exige_formado: false
  palavras_obrigatorias_qualquer: []
  palavras_excluir: []
  publicada_ha_no_maximo_dias: 7
  fontes: [linkedin_guest, gupy, indeed, greenhouse, lever]
  frequencia_alerta: "a cada 6 h"
  score_minimo_para_alerta: 65
```

Perguntas que costumam faltar: raio aceitável para presencial/híbrido; se aceita mudar de cidade; empresas que sonha e empresas que não quer; setores a evitar; nível de inglês real; se a busca deve ser sigilosa em relação ao empregador atual; o que é eliminatório e o que é só preferência.

## Contexto Brasil

CV:
- Não incluir foto, CPF, RG, data de nascimento ou idade, estado civil, filhos, endereço completo (cidade-UF basta) nem pretensão salarial.
- Incluir previsão de formatura (estágio e trainee filtram por isso) e LinkedIn com URL personalizada.
- Gupy: cadastro único lido por agentes de IA, que não muda por vaga. Otimizar o cadastro para o cargo-alvo principal. Para importar, preferir arquivo de 1 coluna, sem imagens, no idioma da vaga, e revisar campo a campo depois.
- Vagas em inglês: ter versão do CV em inglês com os mesmos fatos.

Filtros e elegibilidade:
- **Estágio (Lei 11.788/2008):** até 6 h/dia e 30 h/semana no ensino superior; no estágio não obrigatório, bolsa e auxílio-transporte são obrigatórios; duração máxima de 2 anos na mesma empresa (exceto PcD). Cruzar "disponibilidade de X anos" da vaga com a previsão de formatura e marcar bloqueio. Calcular quando o contrato atual completa 2 anos.
- **Trainee:** costuma exigir formatura dentro de uma janela de datas e tem calendário anual (inscrições meses antes do início). Registrar a janela de formatura do candidato.
- **Salário:** a maioria das vagas não informa. Padrão: não descartar, marcar "salário a confirmar".
- **Remoto:** diferenciar "remoto Brasil" de "remoto com residência em SP" ou outro estado.
- **Títulos:** buscar variações de gênero (Estagiário/Estagiária) e PT/EN (Analista de Dados / Data Analyst / Analista de BI / Business Intelligence / Analytics Engineer).

## Entregáveis

1. `diagnostico.md`
2. `perguntas_entrevista.md` (quando a entrevista não for ao vivo)
3. `fatos.yaml` (atualizado com as respostas)
4. `cv_base.md` + DOCX/PDF + `mapa_fatos.md`
5. `filtros.yaml`
6. Headline do LinkedIn e checklist da Gupy

Ao terminar, avisar que a próxima etapa é a skill `cv-adaptar-vaga`, que usa `fatos.yaml`, `cv_base.md` e `filtros.yaml`.
