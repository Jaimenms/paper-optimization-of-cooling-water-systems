* Otimizacao de redes de distribuicao de agua de resfriamanto
*
* Artigo a ser submetido pare Applied Thermal Envineering
* Autores: Ana Levy, André Hemerly, Jaime Souza
*
* versao 21
*
* 2 - PROJETO DA REDE ORIGINAL COM TODA A PARTE TERMICA NA CONDICAO ORIGINAL DE VAZAO DE FLUIDO QUENTE
*

$Include coolingnetwork_applied_v21_part0

execute_load 'gdx/design_original_simplificado.gdx', y_pi,y_pu,lvalve,k_edge;

* Original
fator_k_he_hot_spe(ihe) = fator_k_he_hot_spe_original(ihe);

Hsat_m.l(m_Merkel)=Hatm;
H_m.l(m_Merkel)=0;
T_w_in.l(ihe)=32;
T_w_out.l(ihe)=40;
T_w_feed.l=40;

model design_original
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
eq_k_he_w
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
eq_fob
* Budget
*eq_budget
/
;

design_original.nodlim=50000;
design_original.optca=1e-4;
design_original.optcr=1e-4;

solve design_original minimizing fob using minlp;
Display 'design_original',
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

ypi_existent(ipipe,n) = y_pi.l(ipipe,n);
ypu_existent(ipump,s) = y_pu.l(ipump,s);

execute_unload 'gdx/design_original.gdx';

* FIM
