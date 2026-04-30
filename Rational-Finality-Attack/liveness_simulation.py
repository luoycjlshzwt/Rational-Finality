import mesa
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42
plt.rcParams['font.family'] = 'Times New Roman'
plt.rcParams['mathtext.fontset'] = 'stix'

plt.rcParams.update({
    "font.family": "Times New Roman",
    'axes.labelweight': 'bold',
    'axes.titleweight': 'bold',
    'font.weight': 'bold',
    'xtick.labelsize': 18,
    'ytick.labelsize': 18,
    'legend.fontsize': 16,
    'axes.linewidth': 2.0
})


# ==========================================
# 1. Validator Agent
# ==========================================
class ValidatorAgent(mesa.Agent):
    def __init__(self, model, stake, risk_threshold, is_dc=False):
        super().__init__(model)
        self.stake = stake
        self.is_dc = is_dc
        self.strategy = "ATTACK" if is_dc else "HONEST"

        self.belief = model.delta_dc
        self.risk_threshold = risk_threshold

    def step(self):
        if self.is_dc:
            return

        obs_signal = self.model.public_signal

        self.belief = (1 - self.model.learning_rate) * self.belief + self.model.learning_rate * obs_signal

        reward_loss_max = self.model.r_att * self.model.ell * self.model.X_max
        reward_loss_min = self.model.r_att * self.model.ell * self.model.X_min
        capital_loss = self.model.X_max - self.model.X_min

        if self.belief < self.risk_threshold:
            barrier_penalty = capital_loss * (1 - self.belief / self.risk_threshold)
            perceived_cost = reward_loss_max + barrier_penalty
        else:
            perceived_cost = reward_loss_min

        if self.model.current_bribe > perceived_cost:
            self.strategy = "ATTACK"
        else:
            self.strategy = "HONEST"


# ==========================================
# 2. RFI Model
# ==========================================
class RFIModel(mesa.Model):
    def __init__(self, N, alpha, delta_dc, r_att, ell, x_max, x_min, learning_rate):
        super().__init__()
        self.num_agents = N
        self.alpha = alpha
        self.delta_dc = delta_dc
        self.r_att = r_att
        self.ell = ell
        self.X_max = x_max
        self.X_min = x_min
        self.learning_rate = learning_rate

        self.public_signal = delta_dc

        self.current_bribe = 0.035
        self.bribe_increment = 0.005

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Actual_W": lambda m: m.calculate_actual_w(),
                "Mean_Belief": lambda m: np.mean([a.belief for a in m.agents]),
                "Current_Bribe": lambda m: m.current_bribe
            }
        )
        risk_vals = np.random.normal(loc=0.20, scale=0.10, size=N)
        risk_vals = np.clip(risk_vals, 0.01, 0.45)

        num_dc = int(N * delta_dc)
        for i in range(N):
            is_dc = (i < num_dc)
            a = ValidatorAgent(self, 1.0 / N, risk_vals[i], is_dc=is_dc)
            self.agents.add(a)

    def calculate_actual_w(self):
        attacking_count = sum(1 for a in self.agents if a.strategy == "ATTACK")
        return attacking_count / self.num_agents

    def step(self):
        self.agents.shuffle_do("step")
        actual_w = self.calculate_actual_w()
        noise = np.random.normal(0, 0.003)
        self.public_signal = np.clip(actual_w + noise, 0, 1)

        if self.public_signal < self.alpha:
            self.current_bribe += self.bribe_increment
        else:
            self.current_bribe = self.r_att * self.ell * self.X_min * 2.0

        self.datacollector.collect(self)


# ==========================================
# 3
# ==========================================

model = RFIModel(
    N=1000000,
    alpha=0.333,
    delta_dc=0.01,
    r_att=0.0005,
    ell=2.03,
    x_max=1.0,
    x_min=0.85,
    learning_rate=0.7
)

EPOCHS = 16
for i in range(EPOCHS):
    model.step()

df = model.datacollector.get_model_vars_dataframe()

# ==========================================
# vis
# ==========================================
fig, ax1 = plt.subplots(figsize=(11, 6), dpi=120)

ax1.axhline(y=0.333, color='#fab1a0', linestyle='--', linewidth=2, label=r'Threshold ($\alpha=1/3$)')
ax1.fill_between(range(len(df)), 0, 0.333, color='#4C78A8', alpha=0.1)
ax1.fill_between(range(len(df)), 0.333, 1.05, color='#F2A541', alpha=0.1)

l1 = ax1.plot(df['Actual_W'], color='#d63031', marker='o', markersize=8, linewidth=3,
              label='Actual Deviating Stake ($W$)')
l2 = ax1.plot(df['Mean_Belief'], color='#0984e3', linestyle='--', linewidth=3,
              label='Mean Posterior Belief ($\hat{W}$)')

ax1.set_xlabel('Epochs', fontsize=18, fontweight='bold')
ax1.set_ylabel('Fraction of Total Deviating Stake', fontsize=18, fontweight='bold')
ax1.set_ylim(0, 1.05)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))

ax2 = ax1.twinx()
l3 = ax2.plot(df['Current_Bribe'], color='#f39c12', marker='s', markersize=6, linestyle='-.', linewidth=2,
              label='Dynamic Bribe (β)')
ax2.set_ylabel('Bribe', fontsize=18, fontweight='bold', color='#e67e22')
ax2.set_ylim(0, 0.15)
ax2.tick_params(axis='y', labelcolor='#e67e22')
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1%}'))

lines = l1 + l2 + l3 + [ax1.lines[0]]
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='center right', frameon=True, shadow=True, fontsize=14)

ax1.annotate('Phase I: Incubation\n(Belief contagion starts)', xy=(1, 0.05), xytext=(1, 0.25),
             arrowprops=dict(arrowstyle='->', color='gray', lw=1.5), fontsize=15)
ax1.annotate('Phase II: Cascade\n(Belief breaks barrier)', xy=(3.5, 0.45), xytext=(3, 0.65),
             arrowprops=dict(arrowstyle='->', color='gray', lw=1.5), fontsize=15)
ax1.annotate('Phase III: Saturation\n(Bribe withdrawn)', xy=(8, 1.0), xytext=(6, 0.85),
             arrowprops=dict(arrowstyle='->', color='gray', lw=1.5), fontsize=15)

plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("simulation.pdf", format='pdf', bbox_inches='tight')
plt.show()
