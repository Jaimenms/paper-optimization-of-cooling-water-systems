# Errata - Optimization of cooling water system hydraulic debottlenecking

> Versão de trabalho em português; a errata formal (em inglês) está em [`../errata.md`](../errata.md).

J.N.M. Souza, A.L.L. Levy, A.L.H. Costa, *Applied Thermal Engineering* 128 (2018) 1531-1542,
https://doi.org/10.1016/j.applthermaleng.2017.09.089

Itens identificados durante a reimplementação independente do modelo (repositório
`coolingnet`), a partir do confronto entre o texto publicado, o código GAMS que gerou os
resultados (`legacy/gams/coolingnetwork_applied_v21_part0.gms`) e a reprodução
numérica das tabelas. Severidade: **alta** = altera números publicados; **média** = lacuna da
formulação sem efeito nos números; **baixa** = tipográfica ou sem consequência.

| Id | Localização no artigo | Problema | Severidade |
|----|-----------------------|----------|------------|
| [E1](#e1) | Seção 2.2.5, texto após a Eq. (34), p. 1536 | Abscissa α₄ impressa como 0,9; resultados calculados com 0,7 | Alta |
| [E2](#e2) | Seção 2.2.5, Eqs. (32)-(36), pp. 1535-1536 | Falta a condição de força motriz positiva `Hsat_m − H_m > 0`; regularização usada no código não é mencionada | Média |
| [E3](#e3) | Seção 2.2.2, Eq. (4), p. 1534 | Expoente de `c` impresso como 1,85 (Hazen-Williams: 1,852) | Baixa |
| [E4](#e4) | Nomenclatura, p. 1532 | Unidade de `H` (entalpia do ar) impressa como J/°C | Baixa |
| [E5](#e5) | Seção 3.1, Tabela 7, p. 1538 | Viscosidade da água listada, mas não utilizada pelo modelo | Baixa |

---

## E1

**Localização.** Seção 2.2.5 (*Cooling tower model*), parágrafo que introduz a Eq. (35):
"the cooling water temperature along the quadrature points (α₁ = 0.1, α₂ = 0.4, α₃ = 0.6,
α₄ = 0.9)".

**Problema.** O código que gerou todos os resultados usou α₄ = **0,7**
(`Parameter alfa_torre(m_Merkel) / 1 0.1, 2 0.4, 3 0.6, 4 0.7 /`). O texto está correto quanto
ao método (quadratura de Tchebycheff de quatro pontos: 0,1; 0,4; 0,6; 0,9), mas as tabelas e
figuras não correspondem ao valor impresso.

**Evidência.** A reimplementação reproduz a Tabela 8 com três casas decimais apenas com
α₄ = 0,7 (temperatura da bacia 32,202 °C na condição inicial e 32,824 °C na atual, idênticas às
listagens GAMS `part2_initial.lst` e `part2_actual.lst`). Com α₄ = 0,9 os valores mudam.

**Impacto numérico.** Recalculado com a reimplementação (solver `nlpbb`, mesmos dados), valores
em kUSD/ano salvo indicação; "publicado" = α₄ = 0,7, "corrigido" = α₄ = 0,9.

Tabela 8 - temperaturas de saída do fluido quente (°C) e penalidades na condição atual:

| Trocador | Inicial publ. | Inicial corr. | Atual publ. | Atual corr. | Penalidade publ. | Penalidade corr. |
|----------|------:|------:|------:|------:|------:|------:|
| E-101 | 63,48 | 63,45 | 65,16 | 65,12 | 1,96 | 1,55 |
| E-102 | 78,39 | 78,35 | 81,59 | 81,54 | 19,82 | 19,25 |
| E-103 | 39,66 | 39,60 | 41,82 | 41,73 | 22,70 | 21,65 |
| E-104 | 40,91 | 40,85 | 42,81 | 42,73 | 22,61 | 21,67 |
| E-105 | 39,75 | 39,69 | 41,53 | 41,45 | 6,62 | 5,64 |
| Total | | | | | **73,71** | **69,75** |

Temperatura da bacia: 32,20 → 32,13 °C (inicial) e 32,82 → 32,72 °C (atual).

Tabela 9 - sem orçamento disponível:

| Grandeza | Publicado | Corrigido |
|----------|------:|------:|
| Vazões ótimas E-101..E-105 (kg/s) | 12,65 / 23,04 / 33,69 / 17,21 / 3,58 | 12,46 / 23,55 / 34,63 / 16,90 / 3,51 |
| Perdas nas válvulas (m) | 0,49 / 3,70 / 1,90 / 0 / 0 | 0,48 / 3,28 / 1,36 / 0 / 0 |
| Penalidade total | 68,40 | 64,33 |
| Função objetivo | 88,87 | 84,76 |
| Redução da penalidade vs. condição atual | 7,2 % | 7,8 % |

Tabelas 10 e 11 e Figs. 9-10 - função objetivo, penalidade e intervenções:

| Caso | Objetivo publ. | Objetivo corr. | Penalidade publ. | Penalidade corr. | Intervenções publ. | Intervenções corr. |
|------|------:|------:|------:|------:|---|---|
| Sem orçamento | 88,87 | 84,76 | 68,40 | 64,33 | válvulas | válvulas |
| 1A (B = 2,625) | 86,93 | 83,75 | 64,18 | 60,97 | tubos 5 e 6 → 8" | idem |
| 1B (B = 4,125) | 85,04 | 83,31 | 54,20 | 52,43 | bomba 4 | bomba 4 |
| 1C (B = 5,250) | 84,77 | 83,18 | 52,85 | 51,18 | bomba 4 + tubo 5 → 8" | bomba 4 + tubo 6 → 8" |
| Caso 1 (ilimitado) | 84,59 | 83,08 | 51,54 | 49,94 | bomba 4 + tubos 5 e 6 → 8" | idem |
| Caso 2 (pen = 40) | 189,78 | 186,14 | 150,57 | 147,00 | bomba 4 + 10 tubos | bomba 4 + 9 tubos |

Reduções de penalidade da Fig. 10 com o valor corrigido: 7,8 % (sem orçamento), 12,6 % (1A),
24,8 % (1B), 26,6 % (1C) e 28,4 % (Caso 1), contra 7,21 / 12,95 / 26,48 / 28,3 / 30,08 %
publicados. As curvas das Figs. 4, 7 e 8 deslocam-se na mesma proporção; os degraus (ordem das
intervenções) permanecem.

**Consequência para as conclusões.** Nenhuma conclusão qualitativa muda: a hierarquia dos casos,
o salto da compra da bomba perto de 3 kUSD/ano e a comparação com a abordagem puramente
hidráulica (Tabela 12, cujas vazões desejadas não dependem da torre) continuam válidas. Os
valores absolutos de penalidade e de função objetivo estão superestimados em 2-6 %.

**Correção sugerida.** Substituir, na Seção 2.2.5, "α₄ = 0.9" por "α₄ = 0.7" acompanhado de
nota de que os resultados numéricos empregaram essa abscissa (que difere do valor 0,9 do método
de Tchebycheff de quatro pontos); ou, alternativamente, informar que os resultados corrigidos
com α₄ = 0,9 são os da tabela acima.

## E2

**Localização.** Seção 2.2.5, Eqs. (32)-(36); especialmente o integrando da Eq. (33),
`1/(Hsat_m − H_m)`.

**Problema.** A formulação não impõe `Hsat_m − H_m > 0` (ar não saturado ao longo do
recheio), condição necessária para que a integral de Merkel tenha significado. Além disso, o
código empregou a regularização `1/(Hsat_m − H_m + 1)` (1 J/kg), não mencionada no artigo. Com
a regularização, o integrando troca de sinal onde a reta de operação cruza a curva de saturação
e a Eq. (32) passa a admitir uma raiz espúria na temperatura de bulbo úmido.

**Evidência.** Durante a reprodução do Caso 2 um solver (Bonmin) convergiu para um projeto com
penalidade nula e custo total de 53,4 kUSD/ano, contra 189,8 kUSD/ano publicados; nesse ponto a
bacia estava a 26,5 °C (= bulbo úmido, aproximação nula) e `Hsat − H = −4,2 kJ/kg` no ponto de
quadratura superior. Adicionada a restrição `Hsat_m − H_m ≥ 100 J/kg`, o mesmo solver reproduz
a solução publicada.

**Impacto nos resultados publicados.** Nenhum. Todas as soluções do artigo satisfazem a condição
com folga (forças motrizes acima de ~40 kJ/kg), pois o SBB/CONOPT partiu de pontos físicos e
não migrou para o outro ramo.

**Consequência.** Leitores que implementarem a formulação tal como publicada, com outro solver
ou outro ponto inicial, podem obter soluções não físicas que aparentam eliminar as penalidades
a custo baixo, contradizendo a discussão da Seção 3.4 ("the solutions do not eliminate the
set-point penalties entirely").

**Correção sugerida.** Acrescentar à formulação a restrição
`Hsat_m − H_m ≥ ε, m = 1, …, 4` (ε pequeno e positivo) e mencionar a regularização numérica
utilizada, ou declarar explicitamente `T_in_w > T_wb` com a condição de ar não saturado.

## E3

**Localização.** Seção 2.2.2, Eq. (4): `fpi_k = 10.67 q_k^1.852 / (c^1.85 D_k^4.8704)`.

**Problema.** O expoente de `c` da equação de Hazen-Williams em unidades SI é 1/0,54 = 1,852,
igual ao de `q`; o valor impresso, 1,85, é um arredondamento. O código usa o valor impresso, de
modo que texto e resultados são consistentes entre si.

**Impacto.** `120^(1,852−1,85) ≈ 1,010`: as perdas de carga nos tubos estão cerca de 1 %
maiores do que com o expoente padrão. Efeito nas vazões e nos custos inferior à precisão das
tabelas; nenhum efeito nas conclusões.

**Correção sugerida.** Escrever `c^1.852` (e, se desejado, mencionar que os cálculos usaram
1,85).

## E4

**Localização.** Nomenclatura, entrada "H air enthalpy (J/°C)".

**Problema.** Unidade incorreta; a entalpia específica do ar é expressa em J/kg (como `Hatm` na
Tabela 7, 71000 J/kg).

**Impacto.** Tipográfico.

## E5

**Localização.** Seção 3.1, Tabela 7, linha "Cooling water viscosity (mPa·s) 0.72".

**Problema.** A viscosidade não entra em nenhuma equação do modelo (perdas de carga por
Hazen-Williams, coeficientes de película por lei de potência a partir das condições de projeto).

**Impacto.** Nenhum; o parâmetro pode ser omitido ou o texto pode esclarecer que ele foi usado
apenas no dimensionamento original dos trocadores (Tabela 6).
