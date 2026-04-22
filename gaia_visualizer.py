# gaia_visualizer.py
# Streamlit one-click runner for GAIA.OS

import sys, json, subprocess, pathlib, random
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="GAIA.OS Visualizer", layout="wide")
st.title("GAIA.OS — Simulation Visualizer")

# --- Controls ---
col1, col2, col3 = st.columns(3)

with col1:
    days = st.number_input("Days", min_value=1, max_value=5000, value=300, step=10)

with col2:
    households = st.number_input("Households", min_value=1, max_value=1000, value=1, step=1)

with col3:
    members = st.number_input("Members/Household", min_value=1, max_value=500, value=20, step=1)

run_btn = st.button("▶️ Run Simulation")

# --- Direct import call ---
def call_main_direct(days: int, seed: int, households: int, members: int):
    """Call main.run_simulation if available (preferred)."""
    try:
        import importlib
        main = importlib.import_module("main")
        if hasattr(main, "run_simulation_artifact"):
            artifact = main.run_simulation_artifact(
                days=days,
                seed=seed,
                num_households=households,
                members_per_household=members
            )
            return artifact.to_dict() if hasattr(artifact, "to_dict") else artifact
        if hasattr(main, "run_simulation"):
            return main.run_simulation(
                days=days,
                seed=seed,
                num_households=households,
                members_per_household=members
            )
        return None
    except Exception as e:
        st.info(f"Direct import path not available: {e}")
        return None

# --- Subprocess fallback ---
def call_main_subprocess(days: int, seed: int, households: int, members: int, out_path: str):
    """Run main.py via subprocess, expecting it to write JSON to out_path."""
    cmd = [
        sys.executable, "main.py",
        "--days", str(days),
        "--seed", str(seed),
        "--households", str(households),
        "--members", str(members),
        "--artifact",
        "--out", out_path
    ]
    subprocess.run(cmd, check=True)
    with open(out_path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- Data normalization ---
def normalize_to_df(results):
    """Convert results into a DataFrame with 'day' as index."""
    if results is None:
        return None
    if hasattr(results, "to_dataframe"):
        return results.to_dataframe()
    if isinstance(results, dict) and "time_series" in results:
        df = pd.DataFrame(results["time_series"])
        if "day" in df.columns:
            df = df.sort_values("day").set_index("day")
        return df
    if isinstance(results, pd.DataFrame):
        df = results.copy()
    elif isinstance(results, list):
        df = pd.DataFrame(results)
    elif isinstance(results, dict):
        df = pd.DataFrame(results)
    else:
        raise ValueError("Unsupported results format.")
    if "day" in df.columns:
        df = df.sort_values("day").set_index("day")
    return df

# --- Plotting helper ---
def plot_series(df: pd.DataFrame, col: str, title: str, ylabel: str):
    if col not in df.columns:
        st.warning(f"Missing '{col}' in results.")
        return
    fig = plt.figure(figsize=(10, 3))  # smaller height
    plt.plot(df.index, df[col])
    plt.title(title)
    plt.xlabel("Day")
    plt.ylabel(ylabel)
    st.pyplot(fig)

# --- Run simulation ---
if run_btn:
    seed = random.randint(0, 10_000_000)  # Always randomize seed
    out_file = str(pathlib.Path("out.json").absolute())

    # Try direct call first
    results = call_main_direct(days, seed, households, members)

    # Fallback to subprocess if needed
    if results is None:
        try:
            results = call_main_subprocess(days, seed, households, members, out_file)
        except subprocess.CalledProcessError as e:
            st.error(f"main.py failed: {e}")
            st.stop()
        except FileNotFoundError:
            st.error("Couldn't find main.py in this folder.")
            st.stop()

    # Normalize to DataFrame
    try:
        df = normalize_to_df(results)
    except Exception as e:
        st.error(f"Could not parse results into a table: {e}")
        st.stop()

    if df is None or df.empty:
        st.warning("Simulation returned no data.")
        st.stop()

    st.success(f"Simulation finished ✅ (Seed = {seed})")
    if isinstance(results, dict) and "metadata" in results:
        metadata = results["metadata"]
        st.write(f"**Mode:** {metadata.get('mode', 'unknown')}")
        st.write(f"**Engine:** {metadata.get('engine_version', 'unknown')}")
    st.write(f"**Initial population:** {households * members} people")
    st.dataframe(df.head(20))

    st.subheader("Charts")
    for col in [c for c in df.columns if c != "day"]:
        plot_series(df, col, f"{col} over time", col)
        st.markdown("---")
