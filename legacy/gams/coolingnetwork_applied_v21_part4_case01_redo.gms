* Otimizacao de redes de distribuicao de agua de resfriamanto
*
* Artigo a ser submetido pare Applied Thermal Envineering
* Autores: Ana Levy, André Hemerly, Jaime Souza
*
* versao 21
*
* 4 - REVAMP COM BUDGET LIMITADO PARA CASO 01
*


$Include coolingnetwork_applied_v21_part0

execute_load 'gdx/design_revamp_case01.gdx',
fator_k_he_hot_spe,
ypi_existent,
ypu_existent,
pen,
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
zq_k_n  ,
vteste,
w_node
;

Scalar quant_testes;
quant_testes = 40;
Scalar incbudget;
incbudget = 7500/quant_testes;
Scalar i_teste;

model design_revamp_lim_budget
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
* Budget
eq_budget
/;

design_revamp_lim_budget.nodlim=50000;
design_revamp_lim_budget.optca=1e-3;
design_revamp_lim_budget.optcr=1e-3;

file foo;

for(i_teste = 11 to 13,
         budget = i_teste*incbudget;

         solve design_revamp_lim_budget minimizing fob using minlp;
         Display i_teste,
         fob.l,
         cope.l,
         cpipe.l,
         cpump.l,
         budget,
         pen,
         k_he_hot.l,
         T_hot_out.l,
         T_hot_out_spe,
         cpen.l,
         che.l,
         q_edge.l,
         k_edge.l,
         f_pi.l,
         f_pu.l,
         f_he.l,
         y_pi.l,
         y_pu.l,
         y_he.l
         T_hot_in,
         T_hot_out.l,
         T_hot_out_spe,
         T_w_in.l,
         T_w_out.l
         ;
         put_utilities foo 'gdxout' / 'gdx/design_revamp_limbudget_case01_' i_teste:0:0;
         execute_unload;
);

