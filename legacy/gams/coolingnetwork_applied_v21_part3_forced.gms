* Otimizacao de redes de distribuicao de agua de resfriamanto
*
* Artigo a ser submetido pare Applied Thermal Envineering
* Autores: Ana Levy, André Hemerly, Jaime Souza
*
* versao 21
*
* 3 - REVAMP COM PENALIDADE
*   CASO 01 - pen = 10000 USD/yoC
*   CASO 02 - pen = 40000 USD/yoC


$Include coolingnetwork_applied_v21_part0

execute_load 'gdx/design_original_actual.gdx',
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
zq_k_n   ,
vteste,
w_node
;

model design_revamp
/
* Unidade de escolhas
eq_ypi_unity
eq_ypu_unity
* Vazoes
eq_k_edge
*eq_q_edge
eq_mass
eq_mass_espec
* Heads
eq_f_he
eq_f_pi
eq_f_pu
* Hidraulica
eq_circ
* Velecidade Máxima
eq_vteste
eq_vmax
eq_vmin
eq_vmax_lim1
eq_vmax_lim2
eq_vmax_lim3
eq_vmax_lim4
* Especificacoes
eq_k_hot
*eq_k_he_w
*eq_T_w_in_spe
*eq_T_hot_out_spe
* Trocadores
eq_cr
eq_h_w
eq_h_hot
eq_U
eq_NTU
eq_epsilon
eq_T_hot_out
eq_T_w_out
* Torre Simplificada
*eq_T_w_in
* Torre Detalhada
eq_Hsat_m
eq_T_w_m
eq_H_m
eq_IM
eq_Ip
eq_Merkel
eq_torre_lim
eq_T_w_in_torre
eq_T_w_base_lim
* Torre
eq_T_w_feed_limit
eq_T_w_feed
* Penalidade
eq_che
eq_penalty_lim1
eq_penalty_lim2
eq_penalty_lim3
eq_penalty_lim4
eq_penalty_lim5
eq_penalty_lim6
* Custos
eq_cope
eq_cpipe
eq_cpump
eq_cpen
* FOB
*eq_fob
eq_fob_w_penalty
eq_forced
* Budget
*eq_budget
/;

design_revamp.nodlim=50000;
design_revamp.optca=1e-3;
design_revamp.optcr=1e-3;

file foo;

cpen_limit = 10000;

Scalar i_teste;
for(i_teste = 1 to 10,
         cpen_limit = cpen_limit + 2500;

         solve design_revamp minimizing fob using minlp;

Display 'design_revamp_case_forced',
cpen_limit,
z_hot_out.l,
T_hot_out.l,
T_hot_out_spe,
T_hot_out_min,
T_hot_out_max,
y_he.l,
pen,
fob.l,
cope.l,
cpipe.l,
cpump.l,
cpen.l,
che.l,
q_edge.l,
k_edge.l,
f_pi.l,
f_pu.l,
f_he.l,
y_pi.l,
y_pi.lo,
y_pu.l,
vteste.l,
w_node.l,
T_hot_in,
T_w_in.l,
T_w_out.l
;
         put_utilities foo 'gdxout' / 'gdx/design_revamp_forced_case_' i_teste:0:0;
         execute_unload;
);
