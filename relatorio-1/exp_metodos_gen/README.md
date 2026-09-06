# estudo_generativo.py

Reprodutibilidade do estudo da seção "Investigação de métodos generativos" (Relatório 1 — caixa planetária de um estágio em FDM). O foco são padrões de transmissão diferentes da planetária.

## O que o script faz

**Módulo A — Otimização topológica do disco cicloidal.**
Método SIMP com filtro de densidade e critérios de otimalidade, baseado no código top88. Disco de referência: 20 lóbulos, raio do círculo de pinos 25 mm, raio dos pinos 2 mm, excentricidade 1 mm, seis pinos de saída. O aro e as buchas são regiões sólidas obrigatórias; os furos de saída são fixos; torque de 1,5 N m aplicado como contato dos pinos da coroa, proporcional ao seno do ângulo na metade carregada. Como o campo de contato gira em relação ao disco, a compliância é somada sobre várias posições angulares (multicaso com fatoração única da rigidez por iteração). A opção `--peca carrier` executa o mesmo procedimento no porta‑satélites da planetária, para comparação.

**Módulo B — Busca combinatória sobre arquiteturas.**
Varredura exaustiva de planetária simples, trem de Wolfrom (3K) e redutor cicloidal, todos com diâmetro externo máximo de 60 mm. Restrições: coaxialidade, condição de montagem, não‑interferência e número mínimo de dentes (17). Para o cicloidal, também são verificados o passo entre pinos e a razão cicloidal (máx. 0,8). O Wolfrom recebe estimativa de rendimento a partir do fator de recirculação.

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

# comparação com o porta‑satélites da planetária
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

O custo do Módulo A cresce com `--nel`: 80 → ~2 s por fração; 150 → ~47 s. `--fases` é quase gratuito, pois a rigidez é fatorada uma única vez por iteração e reutilizada em todos os casos de carga.

## Saídas (diretório `saidas/`)

| Arquivo                     | Conteúdo                                     |
|-----------------------------|----------------------------------------------|
| `topologia_<peca>_vf*.png`  | campo de densidades otimizado                |
| `densidade_<peca>_vf*.npy`  | mesmo campo em array, para pós‑processamento |
| `dominio_<peca>.png`        | conferência das regiões fixas e do domínio   |
| `ot_pareto_<peca>.png`      | compliância normalizada × redução de massa   |
| `ot_resultados_<peca>.csv`  | tabela do Módulo A                           |
| `busca_arquiteturas.png`    | razão de redução × diâmetro externo          |
| `busca_{planetaria,wolfrom,cicloidal}.csv` | soluções viáveis de cada arquitetura |

As figuras usadas na seção do relatório vêm de `topologia_cicloidal_vf50.png`, `ot_pareto_cicloidal.png` e `busca_arquiteturas.png`.

## Resultados de referência

Rodada `--nel 150 --iters 60 --fases 6`:

- Disco maciço: compliância inicial c0 = 9,83 x 10^3 N mm; aro e buchas ocupam 42% da área.
- Para fração de volume 0,50: redução de massa de 29,1% com c/c0 = 1,13, imprimibilidade 0,79.
- Planetária: 144 soluções viáveis, relação de redução máxima 5,18; menor diâmetro externo 42,8 mm.
- Cicloidal: 5821 soluções, redução máxima de 41 para diâmetro até 57,5 mm; redução 20 em apenas 30 mm.
- Wolfrom: 378 soluções, redução máxima 222 com rendimento estimado ~0,44; com rendimento >= 0,70, melhor redução 72.

Para comparação, `--peca carrier` dá 53,1% de redução de massa com c/c0 = 1,13 na fração de volume 0,40: o prato do porta‑satélites tem muito mais material ocioso que o disco cicloidal.

## Limitações

Modelo bidimensional, material isotrópico e linear, sem fadiga. A força de contato é considerada tangencial ao raio do ponto de contato, o que superestima o braço de alavanca efetivo. Folga entre disco e pinos não é modelada, apesar de ser determinante no desempenho real. O campo de densidades é uma sugestão de projeto: exige limiarização e redesenho paramétrico em CAD antes da fabricação.

A condição de montagem aplicada ao Wolfrom é a da planetária simples; satélites compostos exigem também sincronismo angular. O rendimento do Wolfrom é estimado como 1/(1 + fator de recirculação × 0,03) e serve apenas para ordenar candidatos, não para dimensionamento.

## Referências de método

- Sigmund (2001), Struct. Multidisc. Optim. 21(2):120–127 — código de 99 linhas.
- Andreassen et al. (2011), Struct. Multidisc. Optim. 43(1):1–16 — top88, estrutura seguida aqui.
- Ferrari & Sigmund (2020), Struct. Multidisc. Optim. 62(4):2211–2228 — top99neo, versão atual.
- Bendsøe & Sigmund (2004), Topology Optimization, Springer.
- Roozing & Roozing (2022), IROS, pp. 1929–1935 — redutor cicloidal em FDM.
