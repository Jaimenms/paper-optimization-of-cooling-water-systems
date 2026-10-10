* Otimizacao de redes de distribuicao de agua de resfriamanto
*
* Artigo a ser submetido pare Applied Thermal Envineering
* Autores: Ana Levy, André Hemerly, Jaime Souza
*
* versao 21
*
* 1 - PROJETO ORIGINAL SIMPLIFICADO DA REDE ORIGINAL PARA SER USADO COMO ESTIMA
* TIVA INICIAL. MODELO TERMICO NÃO É CONSIDERADO.
*

* Acessando os dados
$Include coolingnetwork_applied_v21_part0

* Definindo o modelo
model design_original_simplificado
/
* Unidade de escolhas
eq_ypi_unity
eq_ypu_unity
* Vazoes
eq_k_edge
eq_q_edge
*eq_mass
*eq_mass_espec
* Heads
eq_f_he
eq_f_pi
eq_f_pu
* Hidraulica
eq_circ
* Velecidade Máxima
eq_vmax
*eq_vmin
eq_vteste
eq_vmax_lim1
eq_vmax_lim2
eq_vmax_lim3
eq_vmax_lim4
* Especificacoes
eq_k_he_w
* Custos
eq_cope
eq_cpipe
eq_cpump
eq_cpen
* FOB
eq_fob
/;

* Ajustando os parametros do método numério (SBB)
design_original_simplificado.Nodlim=500000;
design_original_simplificado.optca=1e-3;
design_original_simplificado.optcr=1e-3;

* Resolvendo para min(FOB)
solve design_original_simplificado minimizing fob using minlp;
Display 'design_original_simplificado',
fob.l,
cope.l,
cpipe.l,
cpump.l,
q_edge.l,
k_edge.l,
vteste.l,
f_pi.l,
f_pu.l,
f_he.l,
y_pi.l,
y_pu.l;

* Guarando o resultado no arquivo GDX
execute_unload 'gdx/design_original_simplificado.gdx';
