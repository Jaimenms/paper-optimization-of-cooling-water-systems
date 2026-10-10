* Otimizacao de redes de distribuicao de agua de resfriamanto
*
* Artigo a ser submetido pare Applied Thermal Envineering
* Autores: Ana Levy, André Hemerly, Jaime Souza
*
* versao 21
*
* 0 - ARQUIVO COM SET, SCALAR, PARAMETER, VARIABLE e EQUATION
*

* Parametros dos métodos numéricos
option nlp=conopt;
option MINLP=sbb;

* sets ========================================================================
* Definição dos indices
* observações:
*  - o indice do circo foi adotado como igual ao indice dos trocadores para
*  simplificar a modelagem no GAMS

Sets
     iedge  edge index   / 1*23 /
     inode  node index   / 1*20 /
     inode_espec(inode) node especification index / 2,3,4,5,6,7,8,9,11,12,13,14,15,16,17,18,19,20 /
     ipump(iedge)  pump edge index / 2 /
     ihe(iedge)    HE edge index   / 19*23 /
     ipipe(iedge)  pipe edge index / 1,3*18 /
     icirc(ihe) hydraulic circ / set.ihe /
     i   pump polynomial index  / 0*2 /
     j   pump cost index        / 0*2 /
     s   pump option      / pu1, pu2, pu3, pu4 /
     n   subsections      / 0_50, 0_75, 1_00, 1_25, 1_50, 2_00, 2_50, 3_00,
                            3_50, 4_00, 5_00, 6_00, 8_00, 10_0, 12_0, 14_0,
                            16_0, 18_0, 20_0, 24_0 /
     m_Merkel  coolling tower integration index / 1*4 /

;

* general parameters ===========================================================
Scalar g gravity acceleration /9.81/;

* design =======================================================================
Scalar vmax maximum flow velocity      /3.7/;
Scalar vmin minimum flow velocity      /0.1/;
Scalar nop  number of operating hours  /8760/;
Scalar pc   energy eq_fob              /0.10/;
Scalar irate interest rate             /0.12/;
Scalar ny project horizon              /20/;
Parameter rfactor annualizing factor ;
         rfactor = irate*((1+irate)**ny+0)/((1+irate)**ny-1)

* water ========================================================================
Scalar rho  specifi weight kg m-3 / 995 /;

* pumps ========================================================================
Scalar eta pump efficiency /0.60/ ;
Scalar fi pump capital eq_fob factor fi /2.8/;
Scalar fms pump capital eq_fob factor fms /1.3/;
Scalar fm pump capital eq_fob factor fm /1.35/;
Table a(i,s) pump curve coefficients
    pu1     pu2      pu3      pu4
0   31.5    37.8     42.00    46.20
1   -135.0  -162.0   -180.0   -198.0
2   -415.6  -498.7   -554.1   -609.5;

Parameter b(j) pump capital eq_fob factor
      /  0  5.1029
         1 -1.2217
         2  0.0771 /;
Parameter qpud(s) pump design mass flow rate design
      /  pu1  0.095276382
         pu2  0.095276382
         pu3  0.095276382
         pu4  0.095276382
          /;

* heat exchanger ===============================================================
Scalar alfa Power-law exponent of the head loss function in heat exchanger /1.852/ ;

Parameter f_he_w_d(ihe) head loss in heat exchanger for design conditions
         / 19 5.53
           20 6.35
           21 4.82
           22 2.97
           23 1.20 /;

Parameter k_he_w_d(ihe) mass flow rate in heat exchanger for design conditions
         / 19 11.8
           20 28.7
           21 35.6
           22 15.6
           23 3.1 /;

Parameter k_he_hot_d(ihe) mass flow rate of hot in heat exchanger for design conditions
         / 19 12
           20 12
           21 10.5
           22 8.5
           23 1.7 /;

Scalar cp_w specific heat capacity of water /4187/;

Parameter cp_hot(ihe) specific heat capacity of hot fluid
         / 19 2200
           20 2000
           21 2840
           22 2200
           23 2200 /;

Parameter T_hot_in_d(ihe) Temperature inlet hot for design conditions
         / 19 80
           20 120
           21 80
           22 69
           23 69 /;

Parameter fator_k_he_hot_spe(ihe) factor to modify k_he_hot_spe
         / 19 1
           20 1
           21 1
           22 1
           23 1 /;

Parameter fator_k_he_hot_spe_original(ihe) factor to modify k_he_hot_spe
         / 19 1
           20 1
           21 1
           22 1
           23 1 /;

Parameter fator_k_he_hot_spe_revamp(ihe) factor to modify k_he_hot_spe
         / 19 1.20
           20 1.20
           21 1.20
           22 1.20
           23 1.20 /;

Parameter T_hot_in(ihe) Temperature inlet hot
         / 19 80
           20 120
           21 80
           22 69
           23 69 /;

Parameter T_hot_out_d(ihe) Temperature outlet hot for design conditions
         / 19 65
           20 80
           21 40
           22 41
           23 41 /;

Parameter T_hot_out_spe(ihe) Temperature outlet hot specified
         / 19 65
           20 80
           21 40
           22 41
           23 41 /;

Parameter T_w_in_spe Temperature inlet water specified / 32 /;

Parameter T_w_out_d Temperature outlet water for design conditions
         / 19 40
           20 40
           21 40
           22 40
           23 40 /;

Parameter A_he(ihe) heat exchanger area
         / 19 27.3
           20 76.7
           21 133.6
           22 109.5
           23 47.4 /;

Parameter h_w_d(ihe) convection heat transfer coefficient of water in heat exchanger h at design condition
         / 19 10615
           20 10651
           21 8864
           22 6187
           23 3645 /;

Parameter h_hot_d(ihe) convection heat transfer coefficient of hot in heat exchanger h at design condition
         / 19 658
           20 266
           21 923
           22 450
           23 216 /;

Parameter Rf_tot(ihe) exchanger fouling resistance
         / 19 0.00051
           20 0.00076
           21 0.00048
           22 0.00049
           23 0.00049 /;

Parameter pen(ihe) penalization factor
         / 19 12500
           20 12500
           21 12500
           22 12500
           23 12500 /;

Parameter pen_case02(ihe) penalization factor
         / 19 40000
           20 40000
           21 40000
           22 40000
           23 40000 /;

Parameter pen_case03(ihe) penalization factor
         / 19 25000
           20 25000
           21 25000
           22 25000
           23 25000 /;

Parameter k_wall tube thermal conductivity / 50 /;

Parameter D_he_ext(ihe) tube external diameter
         / 19 0.02070
           20 0.02070
           21 0.02070
           22 0.02070
           23 0.02070 /;

Parameter D_he_int(ihe) tube internal diameter
         / 19 0.01905
           20 0.01905
           21 0.01905
           22 0.01905
           23 0.01905 /;

Parameter T_hot_out_max maximum hot fluid temperature
         / 19 100
           20 100
           21 100
           22 100
           23 100 /;

Parameter T_hot_out_min  minimum hot fluid temperature
         / 19 20
           20 20
           21 20
           22 20
           23 20 /;

* cooling tower ===============================================================
Parameter T_w_feed_max Maximum Temperature to Tower / 45 /;
Parameter T_w_wb       Wet bulb temperature / 26.5 /;
Parameter epsilon_tower Epsilon of the cooling tower / 0.95 /;
Scalars  a_Hsat / -6.38887667 /
         b_Hsat /  0.86581791 /
         c_Hsat /  15.7153617 /
         d_Hsat /  0.05439778 /
;
Parameters
         Hatm air enthalpy (env temperature 30oC and 60% moisture) / 71000 /
         delta_pack tower pack height/ 2 /
         C_un package parameter / 0.54 /
         n_torre tower factor n/ 0.66 /
         m_air air mass flow rate /63.2/
;

Parameter alfa_torre(m_Merkel) integration abcissas
         /       1       0.1
                 2       0.4
                 3       0.6
                 4       0.7/;

* pipes ========================================================================
Scalar c1    pipe capital eq_fob factor c1 /7.0386/;
Scalar m     pipe capital eq_fob factor m  /1.4393/;
Scalar c_hw  Hazen Williams parameter    /120/;
Parameter dnom(n)  nominal diameter
       /  0_50 0.50
          0_75 0.75
          1_00 1.00
          1_25 1.25
          1_50 1.50
          2_00 2.00
          2_50 2.50
          3_00 3.00
          3_50 3.50
          4_00 4.00
          5_00 5.00
          6_00 6.00
          8_00 8.00
          10_0 10.0
          12_0 12.0
          14_0 14.0
          16_0 16.0
          18_0 18.0
          20_0 20.0
          24_0 24.0 /;
Parameter din(n)  internal diameter
       /  0_50 0.0158
          0_75 0.0210
          1_00 0.0266
          1_25 0.0351
          1_50 0.0409
          2_00 0.0525
          2_50 0.0627
          3_00 0.0779
          3_50 0.0901
          4_00 0.1023
          5_00 0.1282
          6_00 0.1541
          8_00 0.2027
          10_0 0.2545
          12_0 0.3033
          14_0 0.3333
          16_0 0.3810
          18_0 0.4287
          20_0 0.4778
          24_0 0.5746 /;

* Network
Scalar dz the elevation difference between top and botton of cooling tower / 5 /;
Table K(inode,iedge) incidence matrix
               1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18  19  20  21  22  23
           1  -1   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0
           2  +1  -1   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0
           3   0  +1  -1   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0
           4   0   0  +1  -1   0   0   0   0  -1  -1   0   0   0   0   0   0   0   0   0   0   0   0   0
           5   0   0   0  +1  -1   0   0   0   0   0  -1   0   0   0   0   0   0   0   0   0   0   0   0
           6   0   0   0   0  +1   0   0   0   0   0   0  -1  -1   0   0   0   0   0   0   0   0   0   0
           7   0   0   0   0   0  -1   0   0   0   0   0   0   0   0   0   0  +1  +1   0   0   0   0   0
           8   0   0   0   0   0  +1  -1   0   0   0   0   0   0   0   0  +1   0   0   0   0   0   0   0
           9   0   0   0   0   0   0  +1  -1   0   0   0   0   0  +1  +1   0   0   0   0   0   0   0   0
          10   0   0   0   0   0   0   0  +1   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0
          11   0   0   0   0   0   0   0   0  +1   0   0   0   0   0   0   0   0   0  -1   0   0   0   0
          12   0   0   0   0   0   0   0   0   0  +1   0   0   0   0   0   0   0   0   0  -1   0   0   0
          13   0   0   0   0   0   0   0   0   0   0  +1   0   0   0   0   0   0   0   0   0  -1   0   0
          14   0   0   0   0   0   0   0   0   0   0   0  +1   0   0   0   0   0   0   0   0   0  -1   0
          15   0   0   0   0   0   0   0   0   0   0   0   0  +1   0   0   0   0   0   0   0   0   0  -1
          16   0   0   0   0   0   0   0   0   0   0   0   0   0  -1   0   0   0   0  +1   0   0   0   0
          17   0   0   0   0   0   0   0   0   0   0   0   0   0   0  -1   0   0   0   0  +1   0   0   0
          18   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0  -1   0   0   0   0  +1   0   0
          19   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0  -1   0   0   0   0  +1   0
          20   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0   0  -1   0   0   0   0  +1
;
Parameter l(ipipe) pipe length (m)
       / 1   10
         9   25
         10  25
         11  25
         13  25
         14  25
         15  25
         16  25
         18  25
         4   100
         5   100
         6   100
         7   100
         12  125
         17  125
         3   200
         8   200 /;

Parameter ypi_existent(ipipe,n) it is 1 the subsection exists in original network ;
ypi_existent(ipipe,n)=0;
Parameter ypu_existent(ipump,s) it is 1 the subsection exists in original network;
ypu_existent(ipump,s)=0;

Parameter q_edge_max(ipipe);
Parameter q_edge_min(ipipe);
q_edge_max(ipipe)=100;
q_edge_min(ipipe)=0.00001;

* Costs ========================================================================

Parameter cpi(n) pipe section nominal eq_fob ;
          cpi(n) = ((c1/0.3048)*(dnom(n)/12)**m) ;

Parameter fpud(s) pump head design ;
          fpud(s)= sum(i,a(i,s)*(qpud(s))**i.val) ;

Parameter ft(s) pump capital eq_fob factor ft;
      ft(s) = exp(sum(j,b(j)*(log(28710*qpud(s)*fpud(s)**0.5))**j.val)) ;

Parameter zpu(s) pump capital eq_fob factor zpu;
      zpu(s) = 28710*qpud(s)*fpud(s)**0.5 ;

Parameter cpu(s) pump eq_fob ;
      cpu(s) = rfactor*fi*fms*fm*ft(s)*(1.39*exp(8.833-0.6019*log(zpu(s))+0.0519*(log(zpu(s)))**2))  ;

Parameter Budget budget value / 0 /;

Parameter cpen_limit penalty limit / 30000 /;

Parameter k_edge_spe(ihe) penalty limit
/ 19 11.36
  20 52.24
  21 46.22
  22 21.23
  23 3.16 /
*         / 19 11.80
*           20 28.70
*           21 35.60
*           22 15.60
*           23 3.10 /
*         / 19 10.33
*           20 39.35
*           21 50.50
*           22 22.89
*           23 3.37 /
*         / 19 14.16
*           20 34.44
*           21 42.72
*           22 18.72
*           23 3.72 /
;

* Finding circ matrix (LAMBDA) from Incidence Matrix (K)
Parameter LAMBDA(icirc,iedge) hydraulic circ matrix;
Parameter iedge_found teste;
Set jedge(iedge) edge index   / set.iedge /
loop((icirc,ihe),
         if (ord(icirc) eq ord(ihe),
                 LAMBDA(icirc,ihe)=1;
                 iedge_found = ihe.val;
                 while (iedge_found NE 0,
                          loop(jedge,
                                 if (jedge.val EQ iedge_found,
                                   iedge_found = 0;
                                   loop(inode,
                                           if (K(inode,jedge) EQ +1,
                                                   loop(iedge,
                                                           if (K(inode,iedge) EQ -1,
                                                                   LAMBDA(icirc,iedge)=1;
                                                                   iedge_found = iedge.val;
                                                           );
                                                   );
                                           );
                                  );
                                 );
                         );
                 );
                 iedge_found = ihe.val;
                 while (iedge_found NE 0,
                          loop(jedge,
                                 if (jedge.val EQ iedge_found,
                                   iedge_found = 0;
                                   loop(inode,
                                           if (K(inode,jedge) EQ -1,
                                                   loop(iedge,
                                                           if (K(inode,iedge) EQ +1,
                                                                   LAMBDA(icirc,iedge)=1;
                                                                   iedge_found = iedge.val;
                                                           );
                                                   );
                                           );
                                  );
                                 );
                         );
                 );
         );
);

* Defining variables
Positive Variables
vteste(ipipe)
q_edge(iedge)     volumetric flow rate
k_edge(iedge)     massic flow rate
f_pu(ipump,s)     pump head
f_pi(ipipe,n)     pipe head loss per subsection
f_he(ihe)         heat exchanger head loss
q_circ(icirc)     volumetric flow rate per circuit
lvalve(icirc)     valve head loss
cpipe             annualized capital cost of the pipe sections
cpump             annualized capital cost for the pumping system
cpen              annualized overall penalization due higher outlet temperature of hot fluid
cope              overall operating cost of a pump
cr(ihe)           heat capacity ratio
U(ihe)            overall heat transfer coefficient
h_w(ihe)          convection heat transfer coefficient of water
h_hot(ihe)        convection heat transfer coefficient of hot fluid
NTU(ihe)          number of transfer units
epsilon(ihe)      effectiveness of a counter-current flow heat exchanger
k_he_hot(ihe)     mass flow rate of hot fluid in heat exchanger
T_w_feed          water temperature at cooling tower inlet
T_w_base          water temperature at cooling tower outlet
T_w_in(ihe)       water temperature at heat exchanger inlet
T_w_out(ihe)      water temperature at heat exchanger outlet
T_hot_out(ihe)    hot fluid temperature at heat exchanger outlet
che(ihe)          financial loss
IM                integral of Merkel
Ip                characteristic curve of the tower
T_w_m(m_Merkel)   water temperature along cooling tower
Hsat_m(m_Merkel)  saturated air enthalpy along cooling tower
H_m(m_Merkel)     air enthalpy along cooling tower
z_hot_out(ihe)    auxiliary variable for penalization equation
zq_k_n(ipipe,n)   auxiliary variable for vmax equation
;

Free Variables
dummy             dummy objective function
fob               objective function
w_node(inode)     massic flow rate at nodes
;

Binary Variables
y_pi(ipipe,n)     pipe selection binary variable
y_pu(ipump,s)     pump selection binary variable
y_he(ihe)         heat exchanger penalization auxiliar binary vairable
;

* Estimativas iniciais
Hsat_m.l(m_Merkel)=Hatm;
H_m.l(m_Merkel)=0;

* Definindo as equacoes
Equations
* Auxiliares
eq_dummy
* Unidade de escolhas
eq_ypi_unity(ipipe)
eq_ypu_unity(ipump)
* Vazoes
eq_k_edge(iedge)
eq_q_edge(iedge)
* Heads
eq_f_he(ihe)
eq_f_pi(ipipe,n)
eq_f_pu(ipump,s)
* Hidraulica
eq_circ(icirc)
* Velecidade Máxima
eq_vteste(ipipe)
eq_vmax(ipipe)
eq_vmin(ipipe)
eq_vmax_lim1(ipipe,n)
eq_vmax_lim2(ipipe,n)
eq_vmax_lim3(ipipe,n)
eq_vmax_lim4(ipipe,n)
* Especificacoes
eq_k_hot(ihe)
eq_k_he_w(ihe)
eq_T_w_in_spe(ihe)
eq_T_hot_out_spe(ihe)
* Trocadores
eq_cr(ihe)
eq_h_w(ihe)
eq_h_hot(ihe)
eq_U(ihe)
eq_NTU(ihe)
eq_epsilon(ihe)
eq_T_hot_out(ihe)
eq_T_w_out(ihe)
* Torre Simplificada
eq_T_w_in(ihe)
* Torre Detalhada
eq_Hsat_m(m_Merkel)
eq_T_w_m(m_Merkel)
eq_H_m(m_Merkel)
eq_IM
eq_Ip
eq_Merkel
eq_torre_lim
eq_T_w_in_torre(ihe)
eq_T_w_base_lim
* Torre
eq_T_w_feed_limit
eq_T_w_feed
* Penalidade
eq_che(ihe)
eq_penalty_lim1(ihe)
eq_penalty_lim2(ihe)
eq_penalty_lim3(ihe)
eq_penalty_lim4(ihe)
eq_penalty_lim5(ihe)
eq_penalty_lim6(ihe)
* Custos
eq_cope
eq_cpipe
eq_cpump
eq_cpen
* FOB
eq_fob
eq_fob_w_penalty
eq_forced
eq_fob_quad_dif_k
* Budget
eq_budget
eq_no_budget
eq_mass(inode)
eq_mass_espec(inode_espec)
eq_limite_y_pi(ipipe)
;

* Auxiliares
*eq_lvalve_open(ipipe).. 0 =e= lvalve(icirc);
eq_dummy..              dummy =e= 0;

* Unidade de escolhas
eq_ypi_unity(ipipe)..   1 =e= sum(n,y_pi(ipipe,n));
eq_ypu_unity(ipump)..   1 =e= sum(s,y_pu(ipump,s));

* Vazoes
eq_k_edge(iedge)..      k_edge(iedge) =e= rho*q_edge(iedge);
eq_q_edge(iedge)..      q_edge(iedge) =e= sum(icirc,LAMBDA(icirc,iedge)*q_circ(icirc));

* Mass Balance
eq_mass(inode)..        sum(iedge,K(inode,iedge)*k_edge(iedge)) + w_node(inode) =e= 0;
eq_mass_espec(inode_espec).. w_node(inode_espec) =e= 0;

* Heads
eq_f_he(ihe)..          f_he(ihe)       =e= f_he_w_d(ihe)*(k_edge(ihe)/k_he_w_d(ihe))**alfa;
eq_f_pi(ipipe,n)..      f_pi(ipipe,n)   =e= (10.67/(c_hw**1.85))*(q_edge(ipipe)**1.852)/(din(n)**4.8704)*l(ipipe);
eq_f_pu(ipump,s)..      f_pu(ipump,s)       =e= sum(i,a(i,s)*(q_edge(ipump))**i.val) ;

* Hidraulica
eq_circ(icirc)..        0.0 =e= sum(ipump,sum(s,y_pu(ipump,s)*LAMBDA(icirc,ipump)*f_pu(ipump,s))) - dz - sum((ipipe,n),LAMBDA(icirc,ipipe)*f_pi(ipipe,n)*y_pi(ipipe,n)) - sum(ihe,LAMBDA(icirc,ihe)*f_he(ihe)) - lvalve(icirc);

* Velecidade Máxima
eq_vteste(ipipe)..      vteste(ipipe) - sum(n,4*zq_k_n(ipipe,n)/pi/(din(n)**2)) =e= 0;
eq_vmax(ipipe)..        vmax =g= vteste(ipipe);
eq_vmin(ipipe)..        vmin =l= vteste(ipipe);
eq_vmax_lim1(ipipe,n).. zq_k_n(ipipe,n) =g= q_edge(ipipe) - q_edge_max(ipipe)*(1-y_pi(ipipe,n));
eq_vmax_lim2(ipipe,n).. zq_k_n(ipipe,n) =l= q_edge(ipipe) - q_edge_min(ipipe)*(1-y_pi(ipipe,n)) ;
eq_vmax_lim3(ipipe,n).. zq_k_n(ipipe,n) =g= q_edge_min(ipipe)*y_pi(ipipe,n);
eq_vmax_lim4(ipipe,n).. zq_k_n(ipipe,n) =l= q_edge_max(ipipe)*y_pi(ipipe,n) ;



* Especificacoes
eq_k_hot(ihe)..         k_he_hot(ihe) =e= fator_k_he_hot_spe(ihe)*k_he_hot_d(ihe);
eq_k_he_w(ihe)..        k_edge(ihe) =e= k_he_w_d(ihe);
eq_T_w_in_spe(ihe)..    T_w_in(ihe) =e= T_w_in_spe;
eq_T_hot_out_spe(ihe).. T_hot_out(ihe) =e= T_hot_out_spe(ihe);

* Trocadores
eq_cr(ihe)..         cr(ihe)*(k_edge(ihe)*cp_w) =e= (k_he_hot(ihe)*cp_hot(ihe));
eq_h_w(ihe)..        h_w(ihe)   =e= h_w_d(ihe)*(k_edge(ihe)/k_he_w_d(ihe))**0.8;
eq_h_hot(ihe)..      h_hot(ihe) =e= h_hot_d(ihe)*(k_he_hot(ihe)/k_he_hot_d(ihe))**0.6;
eq_U(ihe)..          U(ihe)*(h_hot(ihe)*(D_he_ext(ihe)/D_he_int(ihe)) + (h_w(ihe)*h_hot(ihe)/(2*k_wall))*D_he_ext(ihe)*log(D_he_ext(ihe)/D_he_int(ihe)) + h_w(ihe) + h_w(ihe)*h_hot(ihe)*Rf_tot(ihe) ) =e=  h_w(ihe)*h_hot(ihe) ;
eq_NTU(ihe)..        NTU(ihe)*(k_he_hot(ihe)*cp_hot(ihe)) =e= U(ihe)*A_he(ihe);
eq_epsilon(ihe)..    epsilon(ihe)*((1 + CR(ihe))*(1 - exp(-NTU(ihe)*( sqrt(1+sqr(CR(ihe))) ))) + sqrt(1+sqr(CR(ihe))) * ( (1 + exp(-NTU(ihe)*( sqrt(1+sqr(CR(ihe))) ))) )) =e= 2*(1 - exp(-NTU(ihe)*( sqrt(1+sqr(CR(ihe))) )));
eq_T_hot_out(ihe)..  T_hot_in(ihe)-T_hot_out(ihe) =e= epsilon(ihe)*(T_hot_in(ihe)-T_w_in(ihe));
eq_T_w_out(ihe)..    T_w_out(ihe) =e= T_w_in(ihe) + cr(ihe)*epsilon(ihe)*(T_hot_in(ihe)-T_w_in(ihe));

* Torre Simplificada
eq_T_w_in(ihe)..    (T_w_in(ihe)-T_w_wb)*epsilon_tower =e= (T_w_feed-T_w_in(ihe)) ;

* Torre Detalhada
eq_Hsat_m(m_Merkel)..    Hsat_m(m_Merkel) =e= (a_Hsat + b_Hsat*T_w_m(m_Merkel) + c_Hsat * exp(d_Hsat*T_w_m(m_Merkel)))*1e3;
eq_T_w_m(m_Merkel)..     T_w_m(m_Merkel)   =e= T_w_base + (T_w_feed -T_w_base)*alfa_torre(m_Merkel);
eq_H_m(m_Merkel)..       H_m(m_Merkel)    =e= Hatm + cp_w*rho*sum(ihe,q_edge(ihe))*(T_w_m(m_Merkel)-T_w_base)/m_air;
eq_IM..                  IM =e= (cp_w*(T_w_feed - T_w_base)/4)*sum(m_Merkel,1/(Hsat_m(m_Merkel)-H_m(m_Merkel)+1));
eq_Ip..                  Ip*(rho*sum(ihe,q_edge(ihe))/m_air)**n_torre =e= delta_pack*C_un;
eq_Merkel..              IM =e= Ip;
eq_torre_lim..           T_w_base =l= T_w_feed;
eq_T_w_in_torre(ihe)..   T_w_in(ihe) =e= T_w_base ;
eq_T_w_base_lim..        T_w_base =g= T_w_wb;

* Torre
eq_T_w_feed_limit.. T_w_feed =l= T_w_feed_max;
eq_T_w_feed..       T_w_feed*sum(ihe,k_edge(ihe)) =e= sum(ihe,k_edge(ihe)*T_w_out(ihe));

* Penalidade
eq_che(ihe)..            che(ihe) =e= pen(ihe)*(z_hot_out(ihe) - T_hot_out_spe(ihe)*y_he(ihe));
eq_penalty_lim1(ihe)..   z_hot_out(ihe) =g= T_hot_out(ihe) - T_hot_out_max(ihe)*(1-y_he(ihe)) ;
eq_penalty_lim2(ihe)..   z_hot_out(ihe) =l= T_hot_out(ihe) - T_hot_out_min(ihe)*(1-y_he(ihe)) ;
eq_penalty_lim3(ihe)..   z_hot_out(ihe) =g= T_hot_out_min(ihe)*y_he(ihe) ;
eq_penalty_lim4(ihe)..   z_hot_out(ihe) =l= T_hot_out_max(ihe)*y_he(ihe) ;
eq_penalty_lim5(ihe)..   (T_hot_out(ihe)-T_hot_out_spe(ihe)) =g= (1-y_he(ihe))*(T_hot_out_min(ihe)-T_hot_out_spe(ihe));
eq_penalty_lim6(ihe)..   (T_hot_out(ihe)-T_hot_out_spe(ihe)) =l= (y_he(ihe))*(T_hot_out_max(ihe)-T_hot_out_spe(ihe));

* Custos
eq_cope..               cope   =e= sum(ipump,sum(s,y_pu(ipump,s)*f_pu(ipump,s))*k_edge(ipump)*g/eta*(nop*pc/1000)) ;
eq_cpipe..              cpipe =e= sum((ipipe,n),cpi(n)*y_pi(ipipe,n)*(1-ypi_existent(ipipe,n))*l(ipipe));
eq_cpump..              cpump =e= sum((ipump,s),cpu(s)*y_pu(ipump,s)*(1-ypu_existent(ipump,s)));
eq_cpen..               cpen  =e= sum(ihe,che(ihe));

* FOB
eq_fob..                fob =e= cpipe + cpump + cope;
eq_fob_w_penalty..      fob =e= cpipe + cpump + cope + cpen;
eq_forced..             cpen =l= cpen_limit;
eq_fob_quad_dif_k..       fob =e= 1000*sum(ihe,(k_edge(ihe)-k_edge_spe(ihe))*(k_edge(ihe)-k_edge_spe(ihe)));

* Budget
eq_budget..   cpipe + cpump =l= Budget ;
eq_no_budget.. cpipe + cpump =e= 0;

eq_limite_y_pi(ipipe)..   sum(n,(y_pi(ipipe,n)-ypi_existent(ipipe,n))*din(n)) =g= 0

* FIM *************************************************************************
