# Manual do UrbanCare

Este é o manual de uso do painel UrbanCare, escrito para operadores da central de monitoramento e para gestores das Secretarias de Mobilidade e da concessionária de iluminação. Ele também é o contexto do assistente do painel: o assistente responde com base neste texto e no resumo de dados do dia.

## Visão geral {#visao-geral}

O UrbanCare é um abrigo de ônibus inteligente, pensado para quem espera o ônibus à noite: principalmente mulheres desacompanhadas, mães com crianças e pessoas idosas. Cada abrigo tem sensores e um processador local (Edge AI) que faz três coisas:

1. **Monitora a lotação** do ponto, para que a operação possa despachar um ônibus extra.
2. **Detecta queda de luminosidade**, para abrir chamado de zeladoria com a concessionária de iluminação.
3. **Detecta pessoa vulnerável sozinha à noite**, para sugerir patrulhamento preventivo.

O processamento acontece no próprio abrigo. A câmera gera apenas silhuetas anônimas e contagens; **nenhuma imagem é gravada nem enviada** à central. O painel recebe somente números e alertas.

Quem paga a instalação e a operação são as Secretarias de Mobilidade e as concessionárias de iluminação, por meio de Parceria Público-Privada (PPP). A meta do primeiro ano é instalar 150 abrigos, nos pontos mais vulneráveis do ranking.

## Telas do painel {#telas}

**Mapa.** Mostra todos os pontos de ônibus de rua da cidade, coloridos pela faixa de vulnerabilidade (vermelho = alta, amarelo = média, cinza = baixa). Os abrigos já instalados aparecem com contorno azul. Clique em um ponto para abrir a tela Ponto. Use o filtro de distrito no topo para aproximar o mapa.

**Ranking.** Lista os pontos do mais vulnerável (posição 1) para o menos vulnerável. Cada linha mostra o nome do ponto, o distrito, o índice, a faixa, as ocorrências noturnas próximas e a distância até o poste mais próximo. É possível filtrar por distrito, subprefeitura e faixa, e exportar a lista em CSV.

**Alertas.** Fila dos alertas abertos, do mais recente para o mais antigo. Cada alerta tem tipo, ponto, horário de início e estado (novo, em atendimento, resolvido). Para assumir um alerta, clique em "Atender"; ao concluir, registre a ação tomada e clique em "Resolver". Alertas não atendidos em 15 minutos ficam destacados em laranja.

**Ponto.** Detalhe de um ponto: endereço, distrito, subprefeitura, índice e posição no ranking, gráficos das últimas 24 horas de luminosidade e de lotação, e histórico de alertas. Se o ponto ainda não tem abrigo instalado, a tela mostra só os indicadores do ranking.

**Relatórios.** Resumos por distrito e por subprefeitura (quantidade de pontos, índice médio, pontos na faixa alta, ocorrências noturnas) e a data da última atualização dos dados.

## Alertas: o que significam e o que fazer {#alertas}

**Lotação alta.** A contagem anônima de pessoas no abrigo passou do limite configurado para aquele ponto (padrão: 25 pessoas) por mais de 10 minutos. O que fazer: verificar no sistema da operação se há ônibus atrasado na linha e, se for o caso, solicitar despacho de ônibus extra. Lotação alta é comum nos picos da manhã (por volta das 7h) e do fim da tarde (por volta das 18h).

**Escuridão.** A luminosidade medida no abrigo ficou abaixo de 10 lux à noite, o que indica lâmpada queimada, poste apagado ou falha de energia. O que fazer: abrir chamado de zeladoria com a concessionária de iluminação, informando o ponto e o horário "escuro desde". Se o ponto também está na faixa alta de vulnerabilidade, marque o chamado como prioritário. A tela "pontos escuros agora" lista todos os abrigos nessa situação.

**Pessoa sozinha à noite.** Entre 21h e 5h, o abrigo detectou uma única pessoa esperando por um período prolongado. O alerta não identifica a pessoa, não guarda imagem e não diz nada sobre gênero, idade ou aparência. O que fazer: o alerta é uma **sugestão** de patrulhamento preventivo. A decisão de acionar a Guarda Civil Metropolitana ou outra equipe é sempre de um operador humano, que deve considerar o contexto (por exemplo, horário do próximo ônibus e outros alertas na região). Nunca trate o alerta como suspeita sobre a pessoa: ela é quem está sendo protegida.

**Sensor sem comunicação.** O abrigo não envia leituras há mais de 30 minutos. O que fazer: abrir chamado de manutenção do equipamento. Enquanto isso, os outros alertas desse abrigo não funcionam.

## Índice de vulnerabilidade noturna {#indice}

O índice ordena os pontos de ônibus de rua pela necessidade de um abrigo inteligente. Ele vai de 0 a 1 e combina duas partes:

- **Ocorrências noturnas (peso 0,6):** quantidade de boletins de ocorrência registrados à noite e de madrugada a até 150 metros do ponto, em escala logarítmica (`log(1 + ocorrências) / log(1 + maior valor da cidade)`). A escala logarítmica diferencia bem os pontos com muitas ocorrências e reduz o peso de valores extremos.
- **Escuridão (peso 0,4):** distância até o poste de iluminação pública mais próximo, convertida em percentil entre todos os pontos (quanto mais longe o poste, maior a escuridão).

Só entram no índice boletins de 2025, registrados em via pública, sem crimes contra patrimônio que não atingem quem espera o ônibus (furto de fios e cabos, de veículo, de dentro de veículo e de carga). Cada coordenada exata conta no máximo 10 boletins, para que eventos (shows, festivais) e endereços imprecisos não dominem o ranking.

**Faixas.** As faixas são definidas pela posição no ranking: **alta** = os 10% de pontos mais vulneráveis da cidade; **média** = os 30% seguintes; **baixa** = os 60% restantes. Dizer que um ponto está na faixa alta significa que ele está entre os 10% mais vulneráveis, não que ele seja "perigoso" em termos absolutos.

**Pontos fora do índice.** Paradas dentro de terminais e de corredores ou estações de transferência não entram no ranking: elas têm iluminação própria e estrutura diferente da de um abrigo de rua.

**Como ler o índice com responsabilidade.** O índice indica onde um abrigo inteligente tende a ajudar mais. Ele não mede o caráter de um bairro nem das pessoas que moram ou circulam nele. Boletins de ocorrência refletem também onde as pessoas mais registram ocorrências (mais movimento, mais delegacias, mais confiança na polícia), então regiões com pouca notificação podem estar subestimadas.

## Dados e atualização {#dados}

Os dados do painel são atualizados uma vez por dia, de madrugada, por um pipeline automático (Apache Airflow). As fontes são:

- **Pontos de ônibus e postes de iluminação:** GeoSampa, portal de dados geográficos da Prefeitura de São Paulo.
- **Distritos e subprefeituras:** GeoSampa.
- **Boletins de ocorrência:** Secretaria da Segurança Pública do Estado de São Paulo (SSP-SP), dados abertos de 2025.
- **Leituras dos abrigos (luminosidade, lotação, pessoa sozinha):** nesta versão de demonstração, são **simuladas** para os 150 primeiros pontos do ranking, com sete dias de histórico. Todo registro simulado vem marcado como tal.

A data da última atualização aparece na tela Relatórios. Se ela tiver mais de dois dias, avise a equipe técnica: o pipeline pode ter falhado.

Limitações conhecidas: a SSP-SP não informa a hora exata das ocorrências, apenas o período (noite ou madrugada); a localização de parte dos boletins é aproximada; o cadastro de postes pode não incluir iluminação particular ou de equipamentos públicos.

## Problemas comuns e o que fazer {#problemas}

- **Ponto aparece escuro, mas a equipe em campo diz que está iluminado.** Pode ser sujeira ou obstrução no sensor de luz. Abra chamado de manutenção do abrigo, não de iluminação.
- **Ponto sem gráfico de luminosidade ou lotação.** O ponto ainda não tem abrigo instalado (só os 150 primeiros do ranking têm), ou o sensor está sem comunicação.
- **Ranking mudou de um dia para o outro.** Normal: o índice é recalculado a cada atualização. Mudanças grandes costumam vir de nova carga de dados da SSP-SP ou do cadastro de postes.
- **Distrito não aparece no filtro.** Confira a grafia oficial (por exemplo, "Sé", "Saúde", "Cidade Dutra"). O painel usa os 96 distritos oficiais do município.
- **Muitos alertas de lotação ao mesmo tempo.** Verifique se há interrupção de linha ou de metrô na região; a operação pode precisar de plano de contingência.
- **O assistente não sabe responder.** Ele só usa este manual e o resumo de dados do dia. Para dúvidas fora disso, procure a coordenação da central.

## Privacidade e LGPD {#privacidade}

- O abrigo **não grava imagens** e não envia vídeo. O processamento é local e gera apenas contagens e alertas.
- O sistema **não identifica pessoas**: não há reconhecimento facial, nem coleta de nome, documento, telefone ou placa.
- Os dados de ocorrências usados no índice são agregados por ponto; número do boletim, delegacia e endereço da vítima são descartados no tratamento.
- Operadores não devem registrar dados pessoais nas anotações dos alertas (por exemplo, descrição física de alguém). Registre apenas a ação tomada.
- Pedidos de titulares de dados e dúvidas sobre tratamento de dados devem ser encaminhados ao encarregado (DPO) da Secretaria responsável.
