import mesa
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from tqdm import tqdm


plt.rcParams['pdf.fonttype'] = 42
plt.rcParams['ps.fonttype'] = 42
plt.rcParams['font.family'] = 'Times New Roman'

sns.set_theme(style="white", context="paper", font_scale=1.6)
plt.rcParams.update({
    "font.family": "Times New Roman",
    'axes.labelweight': 'bold',
    'axes.titleweight': 'bold',
    'font.weight': 'bold',
    'xtick.labelsize': 22,    # X 
    'ytick.labelsize': 22,    # Y 
    'legend.fontsize': 21,
    'axes.linewidth': 2.0
})
COLORS = {"Honest": "#56B4E9", "Plateau": "#f39c12", "Crash": "#e74c3c", "Line": "#34495e"}
COLORS1 = {
    "Main": "#4C78A8",      # muted blue
    "Accent": "#F2A541",    # muted amber
    "Dark": "#333333",      
    "Mid": "#666666",       
    "Light": "#BBBBBB"      
}

# ===========================
# 1. Validator Agent
# ===========================
class RationalValidator(mesa.Agent):
    def __init__(self, unique_id, model, stake, risk_factor):
        super().__init__(model)  # Mesa 3.0+
        self.unique_id = unique_id
        self.stake = stake
        self.risk_factor = risk_factor
        self.strategy = "HONEST"

    def calculate_utility(self, strategy, global_W_without_me):
        """
        (Utility Function)
        """
        alpha = self.model.alpha
        X_max = self.model.X_max
        X_min = self.model.X_min
        ell = self.model.ell

        beta_amount = self.model.beta * self.stake

        # 1. Counterfactual Prediction
        my_contribution = self.stake if strategy == "ATTACK" else 0
        W_predicted = global_W_without_me + my_contribution

        # 2. Threshold Effect
        current_price = X_min if W_predicted >= alpha else X_max

        wealth = self.stake * current_price

        if strategy == "ATTACK":
            return wealth + beta_amount
        else:
            mining_reward = self.model.reward_rate * ell * self.stake * self.risk_factor * current_price
            return wealth + mining_reward

    def step(self):
        current_total = self.model.total_deviating_stake
        w_without_me = current_total - (self.stake if self.strategy == "ATTACK" else 0)

        u_honest = self.calculate_utility("HONEST", w_without_me)
        u_attack = self.calculate_utility("ATTACK", w_without_me)

        new_strategy = "ATTACK" if u_attack > u_honest else "HONEST"

        if new_strategy != self.strategy:
            self.strategy = new_strategy
            if new_strategy == "ATTACK":
                self.model.total_deviating_stake += self.stake
            else:
                self.model.total_deviating_stake -= self.stake


class LivenessModel(mesa.Model):
    def __init__(self, N=1000, alpha=0.33, beta=0.01, ell=5, x_min=0.85):
        super().__init__()
        self.num_agents = N
        self.alpha = alpha
        self.beta = beta
        self.ell = ell

        self.X_max = 1.0
        self.X_min = x_min
        self.reward_rate = 0.002

        self.total_deviating_stake = 0.0
        self.agents_list = []

        stake_per_agent = 1.0 / N

        for i in range(N):
            r_factor = np.random.uniform(0.4, 1.3)
            a = RationalValidator(i, self, stake_per_agent, r_factor)
            self.agents_list.append(a)

    def step(self):
        # Asynchronous Update
        np.random.shuffle(self.agents_list)
        for agent in self.agents_list:
            agent.step()


def run_phase_transition():
    betas = np.linspace(0, 0.20, 150)

    results = []

    print("Simulating Phase Transition...")
    for b in tqdm(betas):
        model = LivenessModel(N=1000, alpha=0.33, beta=b, ell=5, x_min=0.85)

        for _ in range(20):
            model.step()

        results.append({
            "Bribe": b,
            "AttackStake": model.total_deviating_stake
        })

    return pd.DataFrame(results)


def run_heatmap():
    betas = np.linspace(0, 0.20, 50)
    ells = np.linspace(1, 15, 15)

    heatmap_data = []

    print("Simulating Heatmap (Phase Space)...")
    for l in tqdm(ells):
        for b in betas:
            model = LivenessModel(N=300, alpha=0.33, beta=b, ell=l, x_min=0.85)
            for _ in range(15): model.step()

            heatmap_data.append({
                "Ell": l,
                "Bribe": b,
                "Disruption": model.total_deviating_stake
            })

    return pd.DataFrame(heatmap_data)


if __name__ == "__main__":
    df_line = run_phase_transition()

    plt.figure(figsize=(11, 7))

    # Shaded Regions
    # Zone 1: Honest (< 1% bribe)
    plt.axvspan(0, 0.01, color=COLORS["Honest"], alpha=0.1)
    # Zone 2: Plateau (1% ~ 15% bribe)
    plt.axvspan(0.01, 0.15, color=COLORS["Plateau"], alpha=0.1)
    # Zone 3: Crash (> 15% bribe)
    plt.axvspan(0.15, 0.20, color=COLORS["Crash"], alpha=0.1)

    sns.lineplot(data=df_line, x="Bribe", y="AttackStake",
                 linewidth=4, color=COLORS["Line"], label="Attack Participation")

    plt.axhline(0.334, color='gray', linestyle='--', linewidth=1.5, alpha=0.8)
    plt.text(0.002, 0.35, r"Liveness Threshold $\alpha=1/3$", color='gray', fontsize=22)

    plt.axvline(0.15, color='red', linestyle=':', linewidth=2, alpha=0.6)
    plt.text(0.13, 0.8, "Crash Cost Bound\n$X_{max}-X_{min}=15\%$", color='black', fontsize=20, rotation=0)

    plt.text(0.005, 0.6, "$\sigma^{allH}$", fontsize=17, color='#0072B2', ha='center', weight='bold')
    plt.text(0.08, 0.6, "$\sigma^{A}$", fontsize=17, color='#d35400', ha='center', weight='bold')
    plt.text(0.08, 0.2, "Under-threshold\nCoordination", fontsize=17, color='#d35400', ha='center')
    plt.text(0.175, 0.6, "$\sigma^{allD}$", fontsize=17, color='darkred', ha='center', weight='bold')

    # plt.title(f"Equilibrium Dynamics", fontsize=18, pad=20)
    plt.xlabel(r"Bribe ($\beta$)", fontsize=20, fontweight='bold')
    plt.ylabel(r"Total Deviating Stake ($W$)", fontsize=20, fontweight='bold')
    plt.xlim(0, 0.20)
    plt.ylim(0, 1.05)

    plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0%}'))
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))

    plt.tight_layout()
    plt.savefig("Q4_1.pdf", format='pdf', bbox_inches='tight')
    plt.show()

    df_heat = run_heatmap()

    matrix = df_heat.pivot(index="Ell", columns="Bribe", values="Disruption")
    X, Y = np.meshgrid(matrix.columns, matrix.index)
    Z = matrix.values

    plt.figure(figsize=(12, 8))

    cp = plt.contourf(X, Y, Z, levels=20, cmap="cividis", alpha=0.8)

    cbar = plt.colorbar(cp)
    cbar.set_label('Attack Participation ($W$)',
                   fontsize=22,
                   fontweight='bold')

    cbar.ax.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f'{x:.0%}')
    )

    CS = plt.contour(X, Y, Z,
                     levels=[0.33],
                     colors=COLORS1["Dark"],
                     linewidths=2,
                     linestyles='--')

    plt.clabel(CS,
               inline=True,
               fmt={0.33: 'Threshold (1/3)'},
               fontsize=20)

    plt.text(0.02, 12,
             "SECURE ZONE",
             color=COLORS1["Dark"],
             fontsize=20,
             bbox=dict(facecolor='white', alpha=0.6, edgecolor='#888888'))

    plt.text(0.14, 4,
             "ATTACK ZONE",
             color=COLORS1["Dark"],
             fontsize=20,
             bbox=dict(facecolor='white', alpha=0.6, edgecolor='#888888'))

    # plt.title("Liveness Stability Phase Space", fontsize=18, pad=20)
    plt.xlabel(r"Bribe ($\beta$)", fontsize=22, fontweight='bold')
    plt.ylabel(r"Attack Window Length ($\ell$)", fontsize=22, fontweight='bold')

    plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.0%}'))

    plt.grid(True, linestyle=':', alpha=0.4, color='black')

    plt.tight_layout()
    plt.savefig("Q4_2.pdf", format='pdf', bbox_inches='tight')
    plt.show()
