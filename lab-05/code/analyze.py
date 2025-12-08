#!/usr/bin/env python3

import os
import argparse
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from scipy import stats

OUTPUT_DIR = "output"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

metrics_path = os.path.join(OUTPUT_DIR, "metrics.txt")

def print_and_write(content="", file_path=metrics_path):
    with open(file_path, "a") as f:
        f.write(content + "\n")
    print(content)

# ---------------------------------------------------------------------
# PARÂMETROS DO SCRIPT
# ---------------------------------------------------------------------
def load_data(path: str) -> pd.DataFrame:
    if path.endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_json(path, lines=True)

    # garante tipos corretos
    df["time_ms"] = pd.to_numeric(df["time_ms"], errors="coerce")
    df["bytes"] = pd.to_numeric(df["bytes"], errors="coerce")

    # adiciona coluna categoria automática
    conds = [
        df["task"] == "simple_user",
        df["task"] == "medium_repo",
        df["task"] == "complex_issues",
    ]
    cats = ["simples", "media", "complexa"]
    df["categoria"] = np.select(conds, cats, default="outro")

    return df


# ---------------------------------------------------------------------
# ESTATÍSTICAS DESCRITIVAS
# ---------------------------------------------------------------------
def estatisticas_basicas(df: pd.DataFrame, coluna: str):
    """Calcula média, mediana, desvio padrão, variância, min, max"""
    return {
        "media": df[coluna].mean(),
        "mediana": df[coluna].median(),
        "desvio_padrao": df[coluna].std(),
        "variancia": df[coluna].var(),
        "min": df[coluna].min(),
        "max": df[coluna].max(),
        "n": df[coluna].count()
    }


# ---------------------------------------------------------------------
# TESTES ESTATÍSTICOS — Alinhados às Hipóteses
# ---------------------------------------------------------------------
def teste_hipotese_one_tailed(gql_values, rest_values):
    """
    t-test unilateral: H1: média(GraphQL) < média(REST)
    """
    # two-tailed t-test
    t_stat, p_two_tail = stats.ttest_ind(gql_values, rest_values, equal_var=False, nan_policy="omit")

    # converte para p unilateral: divide por 2 somente se o efeito está na direção correta
    if t_stat < 0:
        p_one_tail = p_two_tail / 2
    else:
        p_one_tail = 1 - (p_two_tail / 2)

    return t_stat, p_one_tail


# ---------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------
def gerar_graficos(df):
    GRAPHS_DIR = os.path.join(OUTPUT_DIR, "graphs")
    if not os.path.exists(GRAPHS_DIR):
        os.makedirs(GRAPHS_DIR)

    sns.set(style="whitegrid")

    # Fixar ordem da categoria
    df["categoria"] = pd.Categorical(
        df["categoria"],
        categories=["simples", "media", "complexa"],
        ordered=True
    )


    # ============================================================
    # 1) Histograma — REST vs GraphQL
    # ============================================================
    plt.figure(figsize=(10,6))
    sns.histplot(df, x="time_ms", hue="api", bins=40, alpha=0.5)
    plt.title("Histograma de Latência (ms)")
    plt.savefig(os.path.join(GRAPHS_DIR, "hist_latencia.png"), dpi=200)
    plt.close()

    plt.figure(figsize=(10,6))
    sns.histplot(df, x="bytes", hue="api", bins=40, log_scale=True, alpha=0.5)
    plt.title("Histograma de Tamanho (bytes) – escala log")
    plt.savefig(os.path.join(GRAPHS_DIR, "hist_bytes.png"), dpi=200)
    plt.close()

    # ============================================================
    # 2) KDE — Comparação de densidades (corrigido: shade → fill)
    # ============================================================
    plt.figure(figsize=(10,6))
    sns.kdeplot(df[df["api"]=="graphql"]["time_ms"], label="GraphQL", fill=True)
    sns.kdeplot(df[df["api"]=="rest"]["time_ms"], label="REST", fill=True)
    plt.title("Distribuição de densidade — Latência")
    plt.legend()
    plt.savefig(os.path.join(GRAPHS_DIR, "kde_latencia.png"), dpi=200)
    plt.close()

    plt.figure(figsize=(10,6))
    sns.kdeplot(df[df["api"]=="graphql"]["bytes"], label="GraphQL", fill=True)
    sns.kdeplot(df[df["api"]=="rest"]["bytes"], label="REST", fill=True)
    plt.title("Distribuição de densidade — Bytes")
    plt.legend()
    plt.savefig(os.path.join(GRAPHS_DIR, "kde_bytes.png"), dpi=200)
    plt.close()

    # ============================================================
    # 3) Violino + stripplot (substitui swarmplot para evitar warnings)
    # ============================================================
    plt.figure(figsize=(10,6))
    sns.violinplot(data=df, x="api", y="time_ms", inner="quartile")
    sns.stripplot(data=df, x="api", y="time_ms", size=2, jitter=True, color="black", alpha=0.4)
    plt.title("Gráfico de Violino — Latência")
    plt.savefig(os.path.join(GRAPHS_DIR, "violino_latencia.png"), dpi=200)
    plt.close()

    plt.figure(figsize=(10,6))
    sns.violinplot(data=df, x="api", y="bytes", inner="quartile")
    sns.stripplot(data=df, x="api", y="bytes", size=2, jitter=True, color="black", alpha=0.4)
    plt.title("Gráfico de Violino — Bytes")
    plt.savefig(os.path.join(GRAPHS_DIR, "violino_bytes.png"), dpi=200)
    plt.close()

    # ============================================================
    # 4) Barras com erro padrão (mean + IC95) — corrigido
    # ============================================================
    plt.figure(figsize=(10,6))
    sns.barplot(data=df, x="api", y="time_ms", errorbar=("ci", 95))
    plt.title("Média da Latência + IC95")
    plt.savefig(os.path.join(GRAPHS_DIR, "bar_latencia.png"), dpi=200)
    plt.close()

    plt.figure(figsize=(10,6))
    sns.barplot(data=df, x="api", y="bytes", errorbar=("ci", 95))
    plt.title("Média dos Bytes + IC95")
    plt.savefig(os.path.join(GRAPHS_DIR, "bar_bytes.png"), dpi=200)
    plt.close()

    # ============================================================
    # 5) Linha temporal (evolução por repetição)
    # ============================================================
    df_sorted = df.reset_index().sort_values(by="index")

    plt.figure(figsize=(12,6))
    sns.lineplot(data=df_sorted, x="index", y="time_ms", hue="api")
    plt.title("Evolução da Latência ao longo do experimento")
    plt.savefig(os.path.join(GRAPHS_DIR, "linha_latencia.png"), dpi=200)
    plt.close()

    # ============================================================
    # 6) Scatter — relação latência × tamanho
    # ============================================================
    plt.figure(figsize=(10,6))
    sns.scatterplot(data=df, x="bytes", y="time_ms", hue="api")
    plt.title("Relação entre Bytes e Latência")
    plt.savefig(os.path.join(GRAPHS_DIR, "scatter_bytes_vs_latencia.png"), dpi=200)
    plt.close()

    # ============================================================
    # 7) CDF – distribuição acumulada
    # ============================================================
    def plot_cdf(values, label):
        sorted_v = np.sort(values)
        y = np.arange(1, len(sorted_v)+1) / len(sorted_v)
        plt.plot(sorted_v, y, label=label)

    plt.figure(figsize=(10,6))
    plot_cdf(df[df.api=="graphql"]["time_ms"], "GraphQL")
    plot_cdf(df[df.api=="rest"]["time_ms"], "REST")
    plt.title("CDF — Latência")
    plt.xlabel("ms")
    plt.ylabel("Probabilidade acumulada")
    plt.legend()
    plt.savefig(os.path.join(GRAPHS_DIR, "cdf_latencia.png"), dpi=200)
    plt.close()

    # ============================================================
    # 8) NOVO — Latência por categoria (simples, média, complexa)
    # ============================================================
    plt.figure(figsize=(12,6))
    sns.barplot(data=df, x="categoria", y="time_ms", hue="api", errorbar=("ci", 95))
    plt.title("Latência por Categoria de Tarefa (Simples / Média / Complexa)")
    plt.savefig(os.path.join(GRAPHS_DIR, "categoria_vs_latencia.png"), dpi=200)
    plt.close()

    # ============================================================
    # 9) NOVO — Tamanho da resposta por categoria
    # ============================================================
    plt.figure(figsize=(12,6))
    sns.barplot(data=df, x="categoria", y="bytes", hue="api", errorbar=("ci", 95))
    plt.title("Tamanho da Resposta por Categoria de Tarefa (Simples / Média / Complexa)")
    plt.savefig(os.path.join(GRAPHS_DIR, "categoria_vs_bytes.png"), dpi=200)
    plt.close()

    g = sns.FacetGrid(df, col="categoria", hue="api", col_order=["simples", "media", "complexa"])
    g.map(sns.kdeplot, "time_ms", fill=True).add_legend()
    g.fig.suptitle("Distribuição de Latência por Categoria", y=1.02)
    g.savefig(os.path.join(GRAPHS_DIR, "facet_kde_categoria.png"), dpi=200)
    plt.close()

    g = sns.FacetGrid(df, col="categoria", hue="api", col_order=["simples", "media", "complexa"])
    g.map(sns.scatterplot, "bytes", "time_ms").add_legend()
    g.fig.suptitle("Relação Bytes vs Latência por Categoria", y=1.02)
    g.savefig(os.path.join(GRAPHS_DIR, "facet_scatter_categoria.png"), dpi=200)
    plt.close()

# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Análise dos resultados REST vs GraphQL")
    parser.add_argument("--arquivo", type=str, default="output/results.csv")
    args = parser.parse_args()

    df = load_data(args.arquivo)

    if os.path.exists(metrics_path):
        os.remove(metrics_path)

    print(df.head())
    print_and_write("========== Dados Carregados ==========", metrics_path)

    # -----------------------------------------------------------
    # Estatísticas globais por API
    # -----------------------------------------------------------
    print_and_write("========== Estatísticas por API ==========", metrics_path)
    grupos = df.groupby("api")

    for api, grupo in grupos:
        print_and_write(f"\n--- API: {api} ---", metrics_path)
        print_and_write("Latência (ms): " + str(estatisticas_basicas(grupo, "time_ms")), metrics_path)
        print_and_write("Bytes: " + str(estatisticas_basicas(grupo, "bytes")), metrics_path)

    # -----------------------------------------------------------
    # Testes de hipóteses
    # -----------------------------------------------------------
    gql = df[df["api"] == "graphql"]
    rest = df[df["api"] == "rest"]

    print_and_write("========== Testes de Hipóteses ==========", metrics_path)

    # ---- IH1: latência média GraphQL < latência média REST ----
    t_lat, p_lat = teste_hipotese_one_tailed(gql["time_ms"], rest["time_ms"])
    print_and_write(f"IH1 — Latência: GraphQL < REST ?", metrics_path)
    print_and_write(f" t={t_lat:.4f}, p(one-tailed)={p_lat:.4f}", metrics_path)

    # ---- IH2: tamanho médio GraphQL < tamanho médio REST ----
    t_bytes, p_bytes = teste_hipotese_one_tailed(gql["bytes"], rest["bytes"])
    print_and_write(f"IH2 — Tamanho da Resposta: GraphQL < REST ?", metrics_path)
    print_and_write(f" t={t_bytes:.4f}, p(one-tailed)={p_bytes:.4f}", metrics_path)

    # -----------------------------------------------------------
    # Gráficos
    # -----------------------------------------------------------
    print_and_write("Gerando gráficos em ./output ...", metrics_path)
    gerar_graficos(df)

    print_and_write("Análise concluída! Resultados e gráficos disponíveis em output/.", metrics_path)

if __name__ == "__main__":
    main()
