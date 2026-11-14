
import streamlit as st
import pandas as pd
import plotly.express as px

# Page configuration
st.set_page_config(
    page_title="Vana | Credit Risk Dashboard",
    page_icon="📊",
    layout="wide"
)

# Header
st.title("Vana Credit Risk Dashboard")
st.caption("Credit Card Portfolio Intelligence | October 2026")

st.success("Development environment configured successfully!")

# Portfolio KPIs
col1, col2, col3 = st.columns(3)

col1.metric("Active Cards", "11,220")
col2.metric("Portfolio Balance", "Q33.0M")
col3.metric("30+ DPD", "20.1%", delta="9.6 pp", delta_color="inverse")

# Sample delinquency data
data = pd.DataFrame({
    "Month": ["May", "June", "July", "August", "September", "October"],
    "30+ DPD": [10.5, 12.0, 13.8, 15.2, 17.5, 20.1]
})

# Chart
fig = px.line(
    data,
    x="Month",
    y="30+ DPD",
    markers=True,
    title="30+ DPD Evolution"
)

fig.add_hline(
    y=10,
    line_dash="dash",
    annotation_text="Target: 10%"
)

st.plotly_chart(fig, use_container_width=True)
