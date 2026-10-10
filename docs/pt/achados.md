# Três achados da reimplementação que merecem atenção

> Notas de trabalho em português; o estado da reprodução (em inglês) está em
> [`../reproduction.md`](../reproduction.md) e a errata formal em [`../errata.md`](../errata.md).

Documento interno dos autores. Resume o que a reimplementação em Python (`coolingnet`) revelou
sobre o artigo *Optimization of cooling water system hydraulic debottlenecking* (Souza, Levy &
Costa, Applied Thermal Engineering 128 (2018) 1531-1542) e sobre o código GAMS original
(`legacy/gams`). Os itens que configuram erros ou omissões no texto publicado estão
detalhados em [`errata.md`](errata.md), com localização no artigo e impacto numérico.

| # | Achado | Natureza | Impacto nos números publicados |
|---|--------|----------|--------------------------------|
| 1 | Ponto de quadratura da integral de Merkel: texto diz 0,9, código usou 0,7 | **Erro no artigo** (texto inconsistente com os cálculos) | Funções objetivo 1,8-4,6 % mais altas do que seriam com o valor impresso; projetos ótimos praticamente iguais |
| 2 | Raiz espúria da equação de Merkel regularizada (força motriz de entalpia negativa) | **Omissão na formulação** publicada | Nenhum: todas as soluções publicadas são físicas. Risco real para quem reproduzir o modelo com outro solver |
| 3 | Instabilidade do Bonmin (CasADi) neste MINLP | Questão de ferramenta, não do artigo | Nenhum |

---

## 1. Ponto de quadratura da integral de Merkel (0,9 no texto, 0,7 no código)

**O que o artigo diz.** Seção 2.2.5, logo após a Eq. (34): a integral de Merkel é avaliada por
quadratura em quatro pontos, com abscissas α₁ = 0,1, α₂ = 0,4, α₃ = 0,6 e **α₄ = 0,9**. Esses
são os pontos do método de Tchebycheff de quatro pontos, padrão na literatura de torres de
resfriamento (CTI).

**O que o código fez.** O parâmetro `alfa_torre` em `coolingnetwork_applied_v21_part0.gms`
vale `/1 0.1, 2 0.4, 3 0.6, 4 0.7/`. Todas as tabelas e figuras do artigo foram geradas com
esse valor.

**Como foi detectado.** O simulador NumPy e o modelo Pyomo reproduzem a Tabela 8 com três casas
decimais somente com α₄ = 0,7 (por exemplo, temperatura da bacia 32,20 °C na condição inicial).
Com 0,9 a temperatura da bacia passa a 32,13 °C e todas as temperaturas de saída mudam na
segunda casa decimal.

**Impacto.** O ponto 0,7 subestima o integrando perto do topo da torre e, portanto, a
capacidade de resfriamento: a água volta à rede 0,07-0,10 °C mais quente, as penalidades da
condição atual sobem de 69,75 para 73,71 kUSD/ano e todas as funções objetivo sobem entre 1,8 %
e 4,6 %. Os projetos ótimos (bomba e tubos trocados) são os mesmos no Caso 1 e no Caso 1A, e
muito próximos nos demais. As conclusões qualitativas do artigo não mudam. Tabela completa em
[`errata.md`](errata.md#e1).

**Decisão na reimplementação.** O arquivo de configuração mantém 0,7 para reproduzir as
tabelas publicadas (`cooling_tower.quadrature_points`), com o motivo comentado. O notebook
`01_water_shortage` mostra o efeito dos dois valores.

## 2. Raiz espúria da equação de Merkel regularizada

**O que acontece.** O código GAMS (não o artigo) regulariza o integrando de Merkel como
`1/(Hsat_m - H_m + 1)` (1 J/kg) para evitar divisão por zero. Nada na formulação, publicada ou
implementada, exige que a força motriz de entalpia `Hsat_m - H_m` seja positiva. Onde a reta
de operação (Eq. 34) cruza a curva de saturação (Eq. 36), o integrando troca de sinal e a
igualdade `I_M = I_P` (Eq. 32) ganha uma segunda raiz, não física, exatamente no limite
inferior da temperatura da bacia (bulbo úmido, 26,5 °C).

**Como foi detectado.** Na primeira resolução do Caso 2 com Bonmin, o solver encontrou um
projeto com penalidade **zero** e custo total de 53,4 kUSD/ano, contra 189,8 kUSD/ano no
artigo. A verificação independente mostrou água saindo da torre a 26,5 °C (aproximação nula) e
força motriz de -4,2 kJ/kg no topo do recheio: ar supersaturado, solução sem significado físico.
Com a bacia a 26,5 °C os cinco trocadores atendiam o set-point e as penalidades desapareciam.

**Por que não afetou o artigo.** As soluções publicadas têm forças motrizes acima de ~40 kJ/kg
em todos os pontos de quadratura (verificado para as condições inicial e atual e para o Caso 1);
o SBB/CONOPT, partindo de pontos físicos, nunca migrou para o outro ramo. O problema é de
robustez da formulação, não dos resultados.

**Decisão na reimplementação.** O modelo inclui a restrição `Hsat_m - H_m ≥ 100 J/kg` em todos
os pontos de quadratura (`cooling_tower.min_enthalpy_driving_force_J_kg`), inativa nas soluções
publicadas; o simulador seleciona a raiz física com o mesmo critério. Com a restrição, o Caso 2
converge para a solução do artigo (189,76 kUSD/ano). Sugestão de texto para a errata em
[`errata.md`](errata.md#e2).

## 3. Instabilidade do Bonmin (via CasADi) neste problema

**O que acontece.** O Bonmin (branch-and-bound baseado em NLP, com IPOPT) distribuído com as
wheels do CasADi é o análogo instalável via `pip` do par SBB + CONOPT. Ele reproduz o Caso 1 em
cerca de 30 s, mas no Caso 2 aborta de forma irrecuperável (`Uncaught error in Bonmin` ou
segmentation fault, código de saída -11) após algumas centenas de NLPs, mesmo com configuração
conservadora (ramificação *most-fractional*, sem re-soluções aleatórias) e executado em
processo isolado.

**O que isso significa.** Não há erro no artigo: é uma limitação da ferramenta. Como a
reprodutibilidade era requisito, o solver padrão do repositório passou a ser um
branch-and-bound próprio (`coolingnet.optimization.nlpbb`) com nós resolvidos pelo IPOPT,
ramificação SOS1 sobre o catálogo de diâmetros, multi-start nas válvulas e busca local final.
Ele resolve os Casos 1 e 2 em cerca de 5 s cada e reproduz as Tabelas 8 a 12. Bonmin, IPOPT e
SCIP continuam disponíveis como alternativas (`SolverSettings(name=...)`).

**Observação lateral sobre o SCIP.** O solver global SCIP (PySCIPOpt) encontra as soluções
corretas como heurística primal, mas o limite dual deste MINLP não convexo fica próximo de zero
(relaxações fracas das equações térmicas), de modo que a prova de otimalidade global não é
alcançável em tempo útil. Isso vale também para o artigo: as soluções do SBB são ótimos locais,
como a própria reimplementação confirmou ao encontrar valores 0,01-0,02 % menores no Caso 2 e no
Caso 1B.

---

## Outras observações menores

Registradas na errata como itens de baixa severidade:

* Eq. (4): expoente de `c` impresso como 1,85, enquanto o expoente de Hazen-Williams é
  1/0,54 = 1,852 (o mesmo usado para `q`). O código usa 1,85; efeito de ~1 % nas perdas de carga
  dos tubos, consistente entre texto e resultados.
* Nomenclatura: a unidade da entalpia do ar `H` aparece como J/°C; o correto é J/kg.
* Tabela 7 lista a viscosidade da água (0,72 mPa·s), parâmetro que não entra em nenhuma equação
  do modelo.
* A regularização `+1 J/kg` no denominador da Eq. (33) existe no código e não é mencionada no
  artigo (efeito numérico desprezível, mas ligada ao achado 2).
