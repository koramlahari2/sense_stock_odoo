CUSTOM_CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 3rem; max-width: 1200px;}

.kpi-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.kpi-label {font-size: 0.8rem; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: .03em;}
.kpi-value {font-size: 1.8rem; font-weight: 700; color: #111827; margin-top: .2rem;}

.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
}
.badge-done {background: #dcfce7; color: #15803d;}
.badge-waiting {background: #fef9c3; color: #a16207;}
.badge-draft {background: #e5e7eb; color: #374151;}
.badge-ready {background: #dbeafe; color: #1d4ed8;}
.badge-cancelled {background: #fee2e2; color: #b91c1c;}
.badge-low {background: #fee2e2; color: #b91c1c;}
.badge-ok {background: #dcfce7; color: #15803d;}

.app-title {font-size: 1.4rem; font-weight: 700; color: #111827; line-height: 1.5; margin-top: .5rem;}
.app-subtitle {color: #6b7280; font-size: 0.85rem;}
</style>
"""


def badge_html(status: str) -> str:
    cls = {
        "Done": "badge-done", "Waiting": "badge-waiting", "Draft": "badge-draft",
        "Ready": "badge-ready", "Cancelled": "badge-cancelled",
    }.get(status, "badge-draft")
    return f'<span class="badge {cls}">{status}</span>'
