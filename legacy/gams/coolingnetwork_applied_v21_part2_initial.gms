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

execute_load 'gdx/design_original.gdx',
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
zq_k_n,
vteste,
w_node
;

* Forçando mesmo projeto
ypi_existent(ipipe,n) = 0;
ypi_existent('1','10_0') = 1;
ypi_existent('3','12_0') = 1;
ypi_existent('4','12_0') = 1;
ypi_existent('5','6_00') = 1;
ypi_existent('6','6_00') = 1;
ypi_existent('7','10_0') = 1;
ypi_existent('8','12_0') = 1;
ypi_existent('9','4_00') = 1;
ypi_existent('10','8_00') = 1;
ypi_existent('11','6_00') = 1;
ypi_existent('12','6_00') = 1;
ypi_existent('13','2_00') = 1;
ypi_existent('14','4_00') = 1;
ypi_existent('15','6_00') = 1;
ypi_existent('16','6_00') = 1;
ypi_existent('17','6_00') = 1;
ypi_existent('18','2_00') = 1;

ypu_existent(ipump,s) = 0;
ypu_existent('2','pu1') = 1;

y_pi.fx(ipipe,n)=ypi_existent(ipipe,n);
y_pu.fx(ipump,s)=ypu_existent(ipump,s);

* Forcando valvulas abertas
lvalve.fx(icirc)=0;

Hsat_m.l(m_Merkel)=Hatm;
H_m.l(m_Merkel)=0;
T_w_in.l(ihe)=32;
T_w_out.l(ihe)=40;
T_w_feed.l=40;


model design_original
/
eq_dummy
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
* Velocidade Máxima
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
* Trocadores
eq_cr
eq_h_w
eq_h_hot
eq_U
eq_NTU
eq_epsilon
eq_T_hot_out
eq_T_w_out
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
*eq_budget
/
;

design_original.nodlim=50000;
design_original.optca=1e-6;
design_original.optcr=1e-6;

solve design_original minimizing fob using minlp;


Display 'design_original_initial',
pen,
vteste.l,
w_node.l,
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
y_pu.l,
z_hot_out.l,
T_hot_out.l,
T_hot_out_spe,
T_hot_in,
T_w_in.l,
T_w_out.l,
T_w_base.l,
T_w_feed.l
;

y_pi.lo(ipipe,n)=0;
y_pu.lo(ipump,s)=0;
y_pi.up(ipipe,n)=1;
y_pu.up(ipump,s)=1;

lvalve.lo(icirc)=0;
lvalve.up(icirc)=1000;

execute_unload 'gdx/design_original_initial.gdx';

* FIM
