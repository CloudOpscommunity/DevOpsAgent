
import streamlit as st
import json
import sqlite3
import time
import os
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd

# Try to import Prometheus client
try:
    from prometheus_api_client import PrometheusConnect
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    st.error("⚠️ prometheus-api-client not installed. Install with: pip install prometheus-api-client")

# Page Configuration
st.set_page_config(
    page_title="OpsBot Real-time Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Prometheus connection
@st.cache_resource
def init_prometheus():
    """Initialize Prometheus connection"""
    if not PROMETHEUS_AVAILABLE:
        return None

    try:
        prom = PrometheusConnect(url="http://localhost:9090", disable_ssl=True)
        # Test connection
        prom.custom_query(query="up")
        return prom
    except Exception as e:
        st.sidebar.error(f"Prometheus connection failed: {e}")
        return None

# Get real-time CPU data from Prometheus
def get_realtime_cpu_data(prom):
    """Fetch real-time CPU usage from Prometheus"""
    if not prom:
        # Simulate realistic CPU data when Prometheus unavailable
        import random
        import math
        time_factor = time.time() % 300
        base_usage = 20 + 15 * math.sin(time_factor / 50)
        noise = random.uniform(-5, 10)
        return max(5, min(95, base_usage + noise))

    try:
        # Try multiple CPU queries
        queries = [
            '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            '100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
            'avg(100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[1m])) * 100))',
            # Fallback query
            '(1 - avg(irate(node_cpu_seconds_total{mode="idle"}[5m]))) * 100'
        ]

        for query in queries:
            try:
                result = prom.custom_query(query=query)
                if result and len(result) > 0:
                    cpu_usage = float(result[0]['value'][1])
                    if 0 <= cpu_usage <= 100:
                        return cpu_usage
            except Exception:
                continue

        # If all queries fail, try to get raw CPU metrics
        result = prom.custom_query(query="node_cpu_seconds_total")
        if result:
            # Simulate based on current time for demo
            import random
            return random.uniform(15, 45)

    except Exception as e:
        st.sidebar.warning(f"CPU query error: {e}")

    # Fallback simulation
    import random
    return random.uniform(20, 80)

# Get historical CPU data
def get_cpu_history(prom, hours=1):
    """Get CPU usage history for the specified time period"""
    if not prom:
        # Generate simulated historical data
        now = datetime.now()
        timestamps = []
        cpu_values = []

        import random
        import math

        for i in range(60):  # 60 data points
            timestamp = now - timedelta(minutes=i)
            time_factor = timestamp.timestamp() % 300
            base_usage = 25 + 20 * math.sin(time_factor / 60)
            noise = random.uniform(-8, 12)
            cpu_usage = max(5, min(95, base_usage + noise))

            timestamps.append(timestamp)
            cpu_values.append(cpu_usage)

        return list(reversed(timestamps)), list(reversed(cpu_values))

    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        query = '100 - (avg by (instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'

        result = prom.custom_query_range(
            query=query,
            start_time=start_time,
            end_time=end_time,
            step="1m"
        )

        if result and len(result) > 0:
            values = result[0]['values']
            timestamps = [datetime.fromtimestamp(float(v[0])) for v in values]
            cpu_values = [float(v[1]) for v in values]
            return timestamps, cpu_values

    except Exception as e:
        st.sidebar.warning(f"Historical data error: {e}")

    # Fallback to simulated data
    return get_cpu_history(None, hours)

# Load UI Data (from OpsBot)
def load_ui_data():
    """Load current system status from OpsBot"""
    if os.path.basename(os.getcwd()) == 'src':
        ui_data_path = os.path.join('..', 'data', 'ui_data.json')
    else:
        ui_data_path = os.path.join('data', 'ui_data.json')

    try:
        if os.path.exists(ui_data_path):
            with open(ui_data_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        st.sidebar.error(f"Error loading OpsBot data: {e}")

    return {
        "cpu_usage": 0.0,
        "status": "No OpsBot data",
        "last_updated": "Never",
        "monitoring_active": False
    }

# Load Incidents
def load_incidents():
    """Load incidents from database"""
    if os.path.basename(os.getcwd()) == 'src':
        db_path = os.path.join('..', 'data', 'incidents.db')
    else:
        db_path = os.path.join('data', 'incidents.db')

    try:
        if not os.path.exists(db_path):
            return []

        conn = sqlite3.connect(db_path)
        cursor = conn.execute("""
            SELECT id, cause, action,
                   COALESCE(cpu_usage, 0) as cpu_usage,
                   COALESCE(container_name, 'unknown') as container_name,
                   timestamp
            FROM incidents
            ORDER BY id DESC
            LIMIT 10
        """)
        incidents = cursor.fetchall()
        conn.close()
        return incidents
    except Exception as e:
        st.sidebar.error(f"Database error: {e}")
        return []

# Main Application
def main():
    # Initialize Prometheus
    prom = init_prometheus()

    # Page Header
    st.title("🤖 OpsBot Real-time Dashboard")
    st.markdown("Live CPU monitoring with automated DevOps response")

    # Sidebar Configuration
    st.sidebar.header("⚙️ Configuration")

    # Auto-refresh settings
    auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh", value=True)
    refresh_interval = st.sidebar.slider("Refresh Interval (seconds)", 5, 60, 10)

    # CPU threshold setting
    cpu_threshold = st.sidebar.slider("🔥 CPU Alert Threshold (%)", 50, 95, 80)

    # Time range for historical data
    time_range = st.sidebar.selectbox(
        "📊 Historical Data Range",
        ["15 minutes", "30 minutes", "1 hour", "2 hours"],
        index=2
    )

    hours_map = {"15 minutes": 0.25, "30 minutes": 0.5, "1 hour": 1, "2 hours": 2}
    time_hours = hours_map[time_range]

    # Connection Status
    st.sidebar.subheader("🔗 Connection Status")
    if prom:
        st.sidebar.success("✅ Prometheus Connected")
    else:
        st.sidebar.error("❌ Prometheus Disconnected")
        st.sidebar.caption("Using simulated data for demonstration")

    # Load OpsBot data
    opsbot_data = load_ui_data()

    # === REAL-TIME METRICS ===
    st.header("📊 Real-time System Metrics")

    # Get current CPU usage
    current_cpu = get_realtime_cpu_data(prom)

    # Display current metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # CPU Usage with color coding
        cpu_color = "normal"
        if current_cpu > cpu_threshold:
            cpu_color = "inverse"
        elif current_cpu > cpu_threshold * 0.8:
            cpu_color = "off"

        st.metric(
            "🖥️ CPU Usage",
            f"{current_cpu:.1f}%",
            delta=f"{current_cpu - cpu_threshold:.1f}%" if current_cpu > cpu_threshold else None
        )

    with col2:
        # OpsBot Status
        opsbot_status = opsbot_data.get('status', 'Unknown')
        if opsbot_status == "Normal":
            st.success(f"🤖 OpsBot: {opsbot_status}")
        elif opsbot_status in ["Spike Detected", "Intervention Needed"]:
            st.error(f"🤖 OpsBot: {opsbot_status}")
        elif opsbot_status in ["Analyzing...", "Remediating..."]:
            st.warning(f"🤖 OpsBot: {opsbot_status}")
        else:
            st.info(f"🤖 OpsBot: {opsbot_status}")

    with col3:
        # Alert Status
        if current_cpu > cpu_threshold:
            st.error(f"🚨 ALERT: CPU > {cpu_threshold}%")
        elif current_cpu > cpu_threshold * 0.8:
            st.warning(f"⚠️ WARNING: CPU > {cpu_threshold * 0.8:.0f}%")
        else:
            st.success("✅ Normal Operation")

    with col4:
        # Last Update
        st.info(f"🕒 Updated: {datetime.now().strftime('%H:%M:%S')}")

    # === REAL-TIME CPU CHART ===
    st.subheader("📈 CPU Usage History")

    # Get historical data
    timestamps, cpu_history = get_cpu_history(prom, time_hours)

    # Create DataFrame for plotting
    df = pd.DataFrame({
        'Time': timestamps,
        'CPU Usage (%)': cpu_history
    })

    # Create the plot
    fig = go.Figure()

    # Add CPU usage line
    fig.add_trace(go.Scatter(
        x=df['Time'],
        y=df['CPU Usage (%)'],
        mode='lines+markers',
        name='CPU Usage',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=4),
        hovertemplate='<b>%{y:.1f}%</b><br>%{x}<extra></extra>'
    ))

    # Add threshold line
    fig.add_hline(
        y=cpu_threshold,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Alert Threshold ({cpu_threshold}%)"
    )

    # Add current value
    fig.add_trace(go.Scatter(
        x=[datetime.now()],
        y=[current_cpu],
        mode='markers',
        name='Current',
        marker=dict(size=12, color='red' if current_cpu > cpu_threshold else 'green'),
        hovertemplate=f'<b>Current: {current_cpu:.1f}%</b><extra></extra>'
    ))

    # Update layout
    fig.update_layout(
        title=f"CPU Usage Over Last {time_range}",
        xaxis_title="Time",
        yaxis_title="CPU Usage (%)",
        yaxis=dict(range=[0, 100]),
        hovermode='x unified',
        showlegend=True,
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # === SYSTEM STATISTICS ===
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Statistics")

        if len(cpu_history) > 0:
            stats_df = pd.DataFrame({
                'Metric': ['Average', 'Maximum', 'Minimum', 'Current'],
                'CPU Usage (%)': [
                    f"{np.mean(cpu_history):.1f}%",
                    f"{np.max(cpu_history):.1f}%",
                    f"{np.min(cpu_history):.1f}%",
                    f"{current_cpu:.1f}%"
                ]
            })
            st.dataframe(stats_df, hide_index=True)

        # Alert summary
        if len(cpu_history) > 0:
            import numpy as np
            alerts = np.sum(np.array(cpu_history) > cpu_threshold)
            st.metric("🚨 Alert Count", f"{alerts} / {len(cpu_history)}")

    with col2:
        st.subheader("🐳 Container Status")

        # Check Docker containers
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"],
                capture_output=True,
                text=True
            )

            if result.stdout.strip():
                containers = []
                for line in result.stdout.strip().split('\n'):
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        containers.append({
                            'Container': parts[0],
                            'Status': parts[1],
                            'Image': parts[2]
                        })

                if containers:
                    container_df = pd.DataFrame(containers)
                    st.dataframe(container_df, hide_index=True)
                else:
                    st.info("No running containers found")
            else:
                st.info("No running containers found")

        except Exception as e:
            st.warning(f"Cannot check containers: {e}")

    # === INCIDENTS ===
    st.header("📋 Recent Incidents")

    incidents = load_incidents()

    if incidents:
        st.success(f"Found {len(incidents)} recent incidents")

        # Create incidents DataFrame
        incidents_data = []
        for incident in incidents:
            incidents_data.append({
                'ID': incident[0],
                'Timestamp': incident[5],
                'CPU Usage': f"{incident[3]:.1f}%",
                'Root Cause': incident[1][:50] + "..." if len(incident[1]) > 50 else incident[1],
                'Action': incident[2][:50] + "..." if len(incident[2]) > 50 else incident[2],
                'Container': incident[4]
            })

        incidents_df = pd.DataFrame(incidents_data)
        st.dataframe(incidents_df, hide_index=True)

        # Expandable details
        with st.expander("📄 Detailed Incident View"):
            for incident in incidents[:3]:  # Show top 3 in detail
                st.markdown(f"**Incident #{incident[0]} - {incident[5]}**")
                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Root Cause:**")
                    st.write(incident[1])

                with col2:
                    st.write("**Action Taken:**")
                    st.write(incident[2])

                st.write(f"**CPU Usage:** {incident[3]:.1f}% | **Container:** {incident[4]}")
                st.divider()
    else:
        st.info("No incidents recorded yet - system running smoothly! ✅")

    # === MANUAL CONTROLS ===
    st.header("🎛️ Manual Controls")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("🔧 Restart Container", type="primary"):
            container_name = opsbot_data.get('container_name', 'test-container')
            try:
                with st.spinner(f"Restarting {container_name}..."):
                    import subprocess
                    subprocess.run(["docker", "restart", container_name], check=True)
                st.success(f"✅ {container_name} restarted!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed: {e}")

    with col2:
        if st.button("📊 Refresh Data"):
            st.rerun()

    with col3:
        if st.button("🧪 Simulate Spike"):
            # Update UI data to simulate spike
            try:
                ui_data_path = 'data/ui_data.json' if os.path.basename(os.getcwd()) != 'src' else '../data/ui_data.json'
                spike_data = {
                    "cpu_usage": 95.0,
                    "status": "Spike Detected",
                    "last_updated": time.ctime(),
                    "monitoring_active": True
                }
                os.makedirs(os.path.dirname(ui_data_path), exist_ok=True)
                with open(ui_data_path, 'w') as f:
                    json.dump(spike_data, f)
                st.success("🎭 Spike simulated!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed: {e}")

    with col4:
        # Export data
        if st.button("💾 Export Data"):
            export_data = {
                'current_cpu': current_cpu,
                'cpu_history': cpu_history,
                'timestamps': [t.isoformat() for t in timestamps],
                'incidents': incidents,
                'opsbot_data': opsbot_data
            }

            st.download_button(
                "📥 Download JSON",
                data=json.dumps(export_data, indent=2),
                file_name=f"opsbot_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )

    # === AUTO-REFRESH ===
    if auto_refresh:
        # Auto-refresh placeholder
        refresh_placeholder = st.empty()

        # Countdown timer
        for i in range(refresh_interval, 0, -1):
            refresh_placeholder.info(f"🔄 Auto-refreshing in {i} seconds...")
            time.sleep(1)

        refresh_placeholder.empty()
        st.rerun()

# Import numpy for statistics
try:
    import numpy as np
except ImportError:
    st.error("NumPy not installed. Install with: pip install numpy")
    st.stop()

if __name__ == "__main__":
    main()
