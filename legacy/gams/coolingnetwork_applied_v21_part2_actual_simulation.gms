* Otimizacao de redes de distribuicao de agua de resfriamanto
*
* Artigo a ser submetido pare Applied Thermal Envineering
* Autores: Ana Levy, André Hemerly, Jaime Souza
*
* versao 21
*
* 2 - PROJETO DA REDE ORIGINAL COM TODA A PARTE TERMICA NA CONDICAO ATUAL DE VAZAO DE FLUIDO QUENTE
*

$Include coolingnetwork_applied_v21_part0

execute_load 'gdx/design_original_initial.gdx',
fator_k_he_hot_spe,
ypi_existent,
ypu_existent,
y_pi,
y_pu,
y_he,
q_edge,
k_edge,
f_pu  ,
f_pi  ,
f_he  ,
q_circ,
lvalve,
cpipe ,
cpump ,
cpen  ,
cope  ,
cr    ,
U     ,
h_w   ,
h_hot ,
NTU   ,
epsilon  ,
k_he_hot ,
T_w_feed ,
T_w_base ,
T_w_in   ,
T_w_out  ,
T_hot_out,
che      ,
IM       ,
Ip       ,
T_w_m    ,
Hsat_m   ,
H_m      ,
z_hot_out,
zq_k_n ,
vteste,
w_node
;

* Original
fator_k_he_hot_spe(ihe) = fator_k_he_hot_spe_revamp(ihe);

model sim1
/
eq_dummy
eq_T_hot_out_spe
eq_k_hot
eq_T_w_in_spe

eq_k_edge
eq_q_edge

* Trocadores
eq_cr
eq_h_w
eq_h_hot
eq_U
eq_NTU
eq_epsilon
eq_T_hot_out
eq_T_w_out

/
;

sim1.nodlim=50000;
sim1.optca=1e-6;
sim1.optcr=1e-6;

solve sim1 minimizing dummy using minlp;

Display 'sim1',
q_edge.l,
k_edge.l,
z_hot_out.l,
T_hot_out.l,
T_hot_out_spe,
T_hot_in,
T_w_in.l,
T_w_out.l,
T_w_base.l,
T_w_feed.l
;

execute_unload 'gdx/design_original_actual_simulation1.gdx';

model sim2
/
eq_dummy
eq_T_hot_out_spe
eq_k_hot
*eq_T_w_in_spe

eq_k_edge
eq_q_edge

* Trocadores
eq_cr
eq_h_w
eq_h_hot
eq_U
eq_NTU
eq_epsilon
eq_T_hot_out
eq_T_w_out

eq_Hsat_m
eq_T_w_m
eq_H_m
eq_IM
eq_Ip
eq_Merkel
eq_torre_lim
eq_T_w_in_torre
eq_T_w_base_lim

/
;

sim2.nodlim=50000;
sim2.optca=1e-6;
sim2.optcr=1e-6;

solve sim2 minimizing dummy using minlp;

Display 'sim2',
q_edge.l,
k_edge.l,
z_hot_out.l,
T_hot_out.l,
T_hot_out_spe,
T_hot_in,
T_w_in.l,
T_w_out.l,
T_w_base.l,
T_w_feed.l
;

execute_unload 'gdx/design_original_actual_simulation2.gdx';





* FIM
