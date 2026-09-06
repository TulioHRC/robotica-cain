# estudo_generativo.py

Reprodutibilidade do estudo próprio da seção *Investigação de métodos
generativos* (Relatório 1 — caixa planetária de um estágio em FDM). O objeto
do estudo são padrões de transmissão **distintos da planetária**.

## O que o script faz

**Módulo A — Otimização topológica do disco cicloidal.**
SIMP ($E = E_{\min} + x^p(E_0-E_{\min})$, $p=3$) com filtro de densidade e
critérios de otimalidade, na estrutura do `top88`. Disco de referência:
$N=20$ lóbulos, círculo de pinos $R=25$ mm, pinos $R_r=2$ mm, excentricidade
$e=1$ mm, seis pinos de saída. Aro do perfil epitrocoidal e buchas são sólidos
obrigatórios; furos de saída engastados; torque de 1,5 N·m entra como contato
dos pinos da coroa, proporcional a $\operatorname{sen}\phi$ na metade
carregada. Como o campo de contato gira em relação ao disco, a compliância é
somada sobre `--fases` posições angulares (multicaso, com fatoração única da
rigidez por iteração). `--peca carrier` roda o mesmo procedimento no
porta-satélites da planetária, para comparação.

**Módulo B — Busca combinatória sobre arquiteturas.**
Varredura exaustiva de planetária simples, trem de Wolfrom (3K) e redutor
cicloidal, todos sob $D_{\text{ext}} \leq 60$ mm. Restrições: coaxialidade,
montagem $(z_s+z_r)/k \in \mathbb{Z}$, não-interferência, $z \geq 17$; para o
cicloidal, passo entre pinos e razão cicloidal $k_1 = eN/R \leq 0{,}8$. O
Wolfrom recebe estimativa de rendimento a partir do fator de recirculação
$\psi = 1/|1-I_2|$.

## Requisitos

```
python >= 3.9
numpy scipy matplotlib
```

## Uso

```bash
# rodada usada no relatório (~5 min)
python3 estudo_generativo.py --modulo AB --peca cicloidal \
        --nel 150 --iters 60 --fases 6 --volfracs 0.2 0.3 0.4 0.5 0.6

# rodada rápida de verificação (~10 s)
python3 estudo_generativo.py --modulo A --nel 80 --iters 20 --volfracs 0.5

# comparação com o porta-satélites da planetária
python3 estudo_generativo.py --modulo A --peca carrier

# só a busca combinatória (segundos, sem malha)
python3 estudo_generativo.py --modulo B
```

| Argumento    | Padrão                | Descrição                              |
|--------------|-----------------------|----------------------------------------|
| `--modulo`   | `AB`                  | `A`, `B` ou `AB`                       |
| `--peca`     | `cicloidal`           | `cicloidal` ou `carrier`               |
| `--nel`      | `140`                 | elementos por lado da malha            |
| `--iters`    | `60`                  | iterações máximas de OT                |
| `--fases`    | `6`                   | fases do campo de contato (cicloidal)  |
| `--volfracs` | `0.2 0.3 0.4 0.5 0.6` | frações de volume varridas             |

O custo do Módulo A cresce com `--nel`: 80 → ~2 s por fração; 150 → ~47 s.
`--fases` é quase gratuito, pois a rigidez é fatorada uma única vez por
iteração e reutilizada em todos os casos de carga.

## Saídas (diretório `saidas/`)

| Arquivo                     | Conteúdo                                     |
|-----------------------------|----------------------------------------------|
| `topologia_<peca>_vf*.png`  | campo de densidades otimizado                |
| `densidade_<peca>_vf*.npy`  | mesmo campo em array, para pós-processamento |
| `dominio_<peca>.png`        | conferência das regiões fixas e do domínio   |
| `ot_pareto_<peca>.png`      | compliância normalizada × redução de massa   |
| `ot_resultados_<peca>.csv`  | tabela do Módulo A                           |
| `busca_arquiteturas.png`    | razão de redução × diâmetro externo          |
| `busca_{planetaria,wolfrom,cicloidal}.csv` | soluções viáveis de cada arquitetura |

As figuras da seção vêm de `topologia_cicloidal_vf50.png`,
`ot_pareto_cicloidal.png` e `busca_arquiteturas.png`.

## Resultados de referência

Rodada `--nel 150 --iters 60 --fases 6`:

- Disco maciço: $c_0 = 9{,}83\times10^3$ N·mm; aro e buchas ocupam 42 % da área.
- $f_V = 0{,}50$ → **29,1 % menos massa, $c/c_0 = 1{,}13$**, imprimibilidade 0,79.
- Planetária: 144 soluções, $i_{\max} = 5{,}18$; menor envelope viável 42,8 mm.
- Cicloidal: 5821 soluções, $i_{\max} = 41$ em $D \leq 57{,}5$ mm; $i = 20$ em
  apenas 30 mm.
- Wolfrom: 378 soluções, $i_{\max} = 222$ ($\eta \approx 0{,}44$); com
  $\eta \geq 0{,}70$, melhor caso $i = 72$.

Para comparação, `--peca carrier` dá 53,1 % de redução com $c/c_0 = 1{,}13$ em
$f_V = 0{,}40$: o prato do porta-satélites tem muito mais material ocioso que o
disco cicloidal.

## Limitações

Modelo bidimensional, material isotrópico e linear, sem fadiga. A força de
contato é tomada tangencial ao raio do ponto de contato, o que superestima o
braço de alavanca efetivo. Folga entre disco e pinos não é modelada, apesar de
determinante no desempenho real. O campo de densidades é sugestão de projeto:
exige limiarização e redesenho paramétrico em CAD antes do fatiamento.

A condição de montagem aplicada ao Wolfrom é a da planetária simples;
satélites compostos exigem ainda sincronismo angular (*clocking*). O
rendimento do Wolfrom, $\eta = 1/(1 + \psi L)$ com $L = 0{,}03$ por par de
engrenamento, serve para ordenar candidatos, não para dimensionar.

## Referências de método

- Sigmund (2001), *Struct. Multidisc. Optim.* 21(2):120–127 — código de 99 linhas.
- Andreassen et al. (2011), *Struct. Multidisc. Optim.* 43(1):1–16 — `top88`,
  estrutura seguida aqui.
- Ferrari & Sigmund (2020), *Struct. Multidisc. Optim.* 62(4):2211–2228 —
  `top99neo`, versão corrente do código de referência.
- Bendsøe & Sigmund (2004), *Topology Optimization*, Springer.
- Roozing & Roozing (2022), IROS, pp. 1929–1935 — redutor cicloidal em FDM.
