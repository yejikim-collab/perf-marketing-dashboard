# -*- coding: utf-8 -*-
"""
마케팅 채널 데이터 + 앱스플라이어 데이터 EDA 대시보드

raw_data/channel/      -> 날짜별 '*_channel.csv' 저장 위치
raw_data/appsflyer/    -> 날짜별 '*_appsflyer.csv' 저장 위치

두 폴더를 각각 스캔해서 날짜/채널/캠페인/그룹/소재 기준으로 조인, 전처리 후 시각화한다.
매일 해당 폴더에 그날치 CSV만 넣고 새로고침(F5)하면 자동 반영된다.

raw_data에 파일이 없으면(예: 공개 배포판) sample_data/의 데모 데이터로 자동 대체해서 보여준다.
"""

import glob
import os

import pandas as pd
import plotly.express as px
import streamlit as st

STAGE_ORDER = ["노출", "클릭", "구매"]

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CHANNEL_DIR = os.path.join(DATA_DIR, "raw_data", "channel")
APPSFLYER_DIR = os.path.join(DATA_DIR, "raw_data", "appsflyer")
SAMPLE_CHANNEL_DIR = os.path.join(DATA_DIR, "sample_data", "channel")
SAMPLE_APPSFLYER_DIR = os.path.join(DATA_DIR, "sample_data", "appsflyer")
JOIN_KEYS = ["일", "채널", "캠페인", "그룹", "소재"]

# 채널(채널데이터 표기) <-> 미디어소스(앱스플라이어 표기) 매핑
CHANNEL_MAP = {
    "구글": "googleadwords_int",
    "메타": "Facebook Ads",
    "네이버": "naver_search",
}

# 실무 KPI 임계값 (raw_data/NAMING_CONVENTION.md 운영 규칙 확정 전까지 미설정)
ROAS_ALERT_MIN = None  # 예: 1.0 (100%) 미만이면 경고
CPA_ALERT_MAX = None  # 예: 50000 (원) 초과면 경고

# ---------- 디자인 시스템 ----------
FONT_FAMILY = "'Pretendard', -apple-system, BlinkMacSystemFont, 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif"
ACCENT = "#2563EB"
ACCENT_SOFT = "#0EA5A4"
INK = "#0F172A"
MUTED_PALETTE = ["#2563EB", "#0EA5A4", "#F59E0B", "#EF4444", "#8B8FA3", "#7C6BAF"]
HEATMAP_SCALE = [[0, "#EF4444"], [0.5, "#F8FAFC"], [1, "#10B981"]]
# 채널은 매체 브랜드 컬러로 고정해 모든 차트에서 동일하게 인식되도록 함
CHANNEL_COLORS = {"구글": "#4285F4", "메타": "#3B5998", "네이버": "#03C75A"}


def inject_css():
    st.markdown(
        f"""
        <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

        html, body, [class*="st-"], .stApp {{
            font-family: {FONT_FAMILY};
        }}
        [data-testid="stIconMaterial"] {{
            font-family: 'Material Symbols Rounded' !important;
        }}
        .block-container, [data-testid="stAppViewBlockContainer"] {{
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: 1280px;
        }}
        h1 {{
            font-weight: 700;
            letter-spacing: -0.02em;
            color: {INK};
        }}
        h2, h3 {{
            font-weight: 600;
            letter-spacing: -0.01em;
            color: {INK};
            margin-top: 0.2rem;
        }}
        [data-testid="stCaptionContainer"] {{
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.72rem;
            font-weight: 600;
        }}
        [data-testid="stMetric"] {{
            padding: 0.35rem 0;
        }}
        [data-testid="stMetricLabel"] {{
            color: #64748B;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }}
        [data-testid="stMetricValue"] {{
            color: {INK};
            font-weight: 700;
            font-variant-numeric: tabular-nums;
            font-size: clamp(1.15rem, 2vw, 1.8rem) !important;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: unset !important;
        }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 20px !important;
        }}
        div[data-testid="stVerticalBlock"] > div[style*="border"] {{
            border-radius: 20px;
            border-color: rgba(15, 23, 42, 0.08) !important;
            box-shadow: 0 12px 28px -18px rgba(15, 23, 42, 0.18);
            background: #FFFFFF;
        }}
        [data-testid="stSidebar"] {{
            background: #FFFFFF;
            border-right: 1px solid rgba(15, 23, 42, 0.06);
        }}
        .stButton > button {{
            border-radius: 999px;
            border: 1px solid rgba(15, 23, 42, 0.12);
        }}
        hr {{
            border-color: rgba(15, 23, 42, 0.06);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt_compact(n, unit=""):
    abs_n = abs(n)
    if abs_n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B{unit}"
    if abs_n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M{unit}"
    if abs_n >= 1_000:
        return f"{n / 1_000:.1f}K{unit}"
    return f"{n:,.0f}{unit}"


def style_fig(fig, show_legend=True):
    fig.update_layout(
        font=dict(family=FONT_FAMILY, size=13, color="#334155"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=show_legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family=FONT_FAMILY),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEF1F5", zeroline=False)
    return fig


@st.cache_data
def load_data(channel_dir: str, appsflyer_dir: str):
    channel_files = sorted(glob.glob(os.path.join(channel_dir, "*_channel.csv")))
    appsflyer_files = sorted(glob.glob(os.path.join(appsflyer_dir, "*_appsflyer.csv")))

    if not channel_files or not appsflyer_files:
        return None, None, None, channel_files, appsflyer_files

    channel_df = pd.concat(
        (pd.read_csv(f, encoding="utf-8-sig") for f in channel_files),
        ignore_index=True,
    )
    appsflyer_df = pd.concat(
        (pd.read_csv(f, encoding="utf-8-sig") for f in appsflyer_files),
        ignore_index=True,
    )

    channel_df["일"] = pd.to_datetime(channel_df["일"])
    appsflyer_df["일"] = pd.to_datetime(appsflyer_df["일"])

    # 앱스플라이어 쪽 컬럼명을 채널 쪽 기준(채널)으로 정규화
    appsflyer_df = appsflyer_df.rename(columns={"미디어소스": "채널"})
    reverse_map = {v: k for k, v in CHANNEL_MAP.items()}
    appsflyer_df["채널"] = appsflyer_df["채널"].map(reverse_map).fillna(appsflyer_df["채널"])

    merged = pd.merge(
        channel_df,
        appsflyer_df,
        on=JOIN_KEYS,
        how="outer",
        suffixes=("_channel", "_appsflyer"),
        indicator=True,
    )

    # 노출/클릭/비용은 매체(채널) 리포트 기준, 회원가입/구매/구매매출은 앱스플라이어 어트리뷰션 기준으로 통일
    merged = merged.rename(columns={
        "클릭_channel": "클릭",
        "회원가입_appsflyer": "회원가입",
        "구매_appsflyer": "구매",
        "구매매출_appsflyer": "구매매출",
    }).drop(columns=["클릭_appsflyer", "회원가입_channel", "구매_channel", "구매매출_channel"])

    return merged, channel_df, appsflyer_df, channel_files, appsflyer_files


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["CTR"] = (df["클릭"] / df["노출"]).replace([float("inf")], None)
    df["CVR"] = (df["구매"] / df["클릭"]).replace([float("inf")], None)
    df["CPA"] = (df["비용"] / df["구매"]).replace([float("inf")], None)
    df["ROAS"] = (df["구매매출"] / df["비용"]).replace([float("inf")], None)
    return df


st.set_page_config(page_title="채널 x 앱스플라이어 대시보드", layout="wide")
inject_css()
st.title("채널 데이터 x 앱스플라이어 데이터 대시보드")
st.caption("일 · 채널 · 캠페인 · 그룹 · 소재 기준 조인 리포트")

merged, channel_df, appsflyer_df, channel_files, appsflyer_files = load_data(CHANNEL_DIR, APPSFLYER_DIR)

using_sample = False
if merged is None:
    merged, channel_df, appsflyer_df, channel_files, appsflyer_files = load_data(
        SAMPLE_CHANNEL_DIR, SAMPLE_APPSFLYER_DIR
    )
    using_sample = True

with st.sidebar:
    st.header("데이터 소스")
    if using_sample:
        st.caption(f"sample_data/ 데모 데이터 {len(channel_files)}개 / {len(appsflyer_files)}개 사용 중")
    else:
        st.caption(f"raw_data/channel {len(channel_files)}개 / raw_data/appsflyer {len(appsflyer_files)}개 인식됨")
    for f in channel_files:
        st.text(f"- {os.path.basename(f)}")
    for f in appsflyer_files:
        st.text(f"- {os.path.basename(f)}")
    if st.button("데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

if merged is None:
    st.warning("raw_data/channel, raw_data/appsflyer 폴더에 각각 날짜별 CSV 파일을 넣어주세요.")
    st.stop()

if using_sample:
    st.info("raw_data에 실제 데이터가 없어 sample_data/의 데모 데이터를 표시하고 있습니다. "
            "raw_data에 파일을 넣으면 자동으로 실데이터로 전환됩니다.")

unmatched = merged[merged["_merge"] != "both"]
if len(unmatched) > 0:
    st.warning(
        f"조인 키(일/채널/캠페인/그룹/소재)가 양쪽에서 매칭되지 않은 행이 {len(unmatched)}건 있습니다. "
        "사이드바 하단 표에서 확인하세요."
    )

df = add_metrics(merged[merged["_merge"] == "both"])

# ---------- 필터 ----------
st.sidebar.header("필터")
min_date, max_date = df["일"].min(), df["일"].max()
date_range = st.sidebar.date_input("기간", (min_date, max_date), min_value=min_date, max_value=max_date)
channels = st.sidebar.multiselect("채널", sorted(df["채널"].unique()), default=sorted(df["채널"].unique()))
campaigns = st.sidebar.multiselect("캠페인", sorted(df["캠페인"].unique()), default=sorted(df["캠페인"].unique()))

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    df = df[(df["일"] >= start) & (df["일"] <= end)]
df = df[df["채널"].isin(channels) & df["캠페인"].isin(campaigns)]

if df.empty:
    st.info("필터 조건에 해당하는 데이터가 없습니다.")
    st.stop()

# 소재명 접두사(VID/IMG/CRS/TXT 등)를 소재 포맷으로 사용
df["소재유형"] = df["소재"].str.split("_").str[0]


def daily_totals(frame):
    return frame.groupby("일")[["노출", "클릭", "비용", "구매", "구매매출"]].sum().sort_index()


def pct_delta(current, previous):
    if previous in (0, None) or pd.isna(previous):
        return None
    d = (current - previous) / previous
    return f"{d:+.1%}"


tab_summary, tab_channel, tab_creative, tab_quality = st.tabs(
    ["요약", "채널·예산", "캠페인·소재", "이상탐지·데이터품질"]
)

# ================= 탭 1: 요약 =================
with tab_summary:
    totals = daily_totals(df)
    today = totals.iloc[-1]
    yesterday = totals.iloc[-2] if len(totals) >= 2 else None

    impressions, clicks, cost = today["노출"], today["클릭"], today["비용"]
    purchases, revenue = today["구매"], today["구매매출"]
    ctr = clicks / impressions if impressions else None
    roas = revenue / cost if cost else None
    cpa = cost / purchases if purchases else None

    with st.container(border=True):
        st.caption("핵심 지표 (선택 기간 마지막 날 기준)")
        row1 = st.columns(3)
        row1[0].metric("노출", fmt_compact(impressions),
                        pct_delta(impressions, yesterday["노출"]) if yesterday is not None else None,
                        help=f"{impressions:,.0f}")
        row1[1].metric("클릭", fmt_compact(clicks),
                        pct_delta(clicks, yesterday["클릭"]) if yesterday is not None else None,
                        help=f"{clicks:,.0f}")
        row1[2].metric("CTR", f"{ctr:.2%}" if ctr is not None else "N/A")

        row2 = st.columns(3)
        row2[0].metric("비용", fmt_compact(cost, "원"),
                        pct_delta(cost, yesterday["비용"]) if yesterday is not None else None,
                        help=f"{cost:,.0f}원")
        row2[1].metric("구매", fmt_compact(purchases),
                        pct_delta(purchases, yesterday["구매"]) if yesterday is not None else None,
                        help=f"{purchases:,.0f}")
        row2[2].metric("ROAS", f"{roas:.1%}" if roas is not None else "N/A", help=f"매출 {revenue:,.0f}원")

        if yesterday is None:
            st.caption("전일 대비 변화율은 데이터가 2일 이상 쌓이면 자동으로 표시됩니다 (현재 1일치).")

    st.write("")

    alerts = []
    if ROAS_ALERT_MIN is not None and roas is not None and roas < ROAS_ALERT_MIN:
        alerts.append(f"ROAS {roas:.1%}가 목표치 {ROAS_ALERT_MIN:.0%} 미달")
    if CPA_ALERT_MAX is not None and cpa is not None and cpa > CPA_ALERT_MAX:
        alerts.append(f"CPA {cpa:,.0f}원이 상한선 {CPA_ALERT_MAX:,.0f}원 초과")

    if alerts:
        st.error("이상 신호 감지  \n" + "  \n".join(f"- {a}" for a in alerts))
    else:
        st.info("이상 신호 없음" if (ROAS_ALERT_MIN or CPA_ALERT_MAX) else
                "⚠ KPI 임계값이 아직 설정되지 않아 이상 신호를 판단할 수 없습니다 (raw_data/NAMING_CONVENTION.md 참고)")

# ================= 탭 2: 채널·예산 =================
with tab_channel:
    with st.container(border=True):
        st.subheader("채널별 비용 · 매출 비중")
        col1, col2 = st.columns(2)
        by_channel = df.groupby("채널", as_index=False).agg(비용=("비용", "sum"), 구매매출=("구매매출", "sum"))
        with col1:
            st.caption("비용 비중")
            fig = px.pie(by_channel, names="채널", values="비용", hole=0.55, color="채널",
                         color_discrete_map=CHANNEL_COLORS)
            st.plotly_chart(style_fig(fig), use_container_width=True)
        with col2:
            st.caption("구매매출 비중")
            fig = px.pie(by_channel, names="채널", values="구매매출", hole=0.55, color="채널",
                         color_discrete_map=CHANNEL_COLORS)
            st.plotly_chart(style_fig(fig), use_container_width=True)

    st.write("")

    with st.container(border=True):
        st.subheader("채널별 퍼널 (노출 → 클릭 → 구매)")
        funnel_df = df.groupby("채널", as_index=False)[STAGE_ORDER].sum().melt(
            id_vars="채널", value_vars=STAGE_ORDER, var_name="단계", value_name="값"
        )
        funnel_df["단계"] = pd.Categorical(funnel_df["단계"], categories=STAGE_ORDER, ordered=True)
        fig = px.funnel(funnel_df, x="값", y="단계", color="채널", color_discrete_map=CHANNEL_COLORS)
        st.plotly_chart(style_fig(fig), use_container_width=True)

    st.write("")

    with st.container(border=True):
        st.subheader("캠페인 x 타겟그룹 ROAS 히트맵")
        pivot = df.pivot_table(index="캠페인", columns="그룹", values="ROAS", aggfunc="mean")
        fig = px.imshow(pivot, text_auto=".0%", color_continuous_scale=HEATMAP_SCALE, aspect="auto")
        st.plotly_chart(style_fig(fig, show_legend=False), use_container_width=True)

    st.write("")

    with st.container(border=True):
        st.subheader("소재별 비용 대비 매출 효율")
        by_creative_eff = df.groupby(["채널", "캠페인", "그룹", "소재"], as_index=False).agg(
            비용=("비용", "sum"), 구매매출=("구매매출", "sum"), 구매=("구매", "sum"),
        )
        fig = px.scatter(by_creative_eff, x="비용", y="구매매출", size="구매", color="채널",
                          color_discrete_map=CHANNEL_COLORS, hover_data=["캠페인", "그룹", "소재"])
        st.plotly_chart(style_fig(fig), use_container_width=True)

# ================= 탭 3: 캠페인·소재 =================
with tab_creative:
    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            st.subheader("소재 포맷별 CTR / CVR")
            by_format = df.groupby("소재유형", as_index=False).agg(
                노출=("노출", "sum"), 클릭=("클릭", "sum"), 구매=("구매", "sum"),
            )
            by_format["CTR"] = by_format["클릭"] / by_format["노출"]
            by_format["CVR"] = by_format["구매"] / by_format["클릭"]
            fig = px.bar(
                by_format.melt(id_vars="소재유형", value_vars=["CTR", "CVR"], var_name="지표", value_name="값"),
                x="소재유형", y="값", color="지표", barmode="group",
                color_discrete_sequence=[ACCENT, ACCENT_SOFT],
            )
            st.plotly_chart(style_fig(fig), use_container_width=True)

    with col4:
        with st.container(border=True):
            st.subheader("타겟그룹별 ROAS")
            by_group = df.groupby("그룹", as_index=False).agg(
                클릭=("클릭", "sum"), 구매=("구매", "sum"), 비용=("비용", "sum"), 구매매출=("구매매출", "sum"),
            )
            by_group["CVR"] = by_group["구매"] / by_group["클릭"]
            by_group["ROAS"] = by_group["구매매출"] / by_group["비용"]
            fig = px.bar(by_group, x="그룹", y="ROAS", hover_data=["CVR"],
                         color_discrete_sequence=[ACCENT])
            st.plotly_chart(style_fig(fig, show_legend=False), use_container_width=True)

    st.write("")

    with st.container(border=True):
        st.subheader("소재 피로도 추이 (CTR 변화)")
        n_dates = df["일"].nunique()
        if n_dates < 2:
            st.info(f"소재 피로도는 최소 2일치 데이터가 필요합니다 (현재 {n_dates}일치). "
                     "데이터가 쌓이면 자동으로 추이 차트가 표시됩니다.")
        else:
            trend = df.groupby(["일", "소재"], as_index=False).agg(노출=("노출", "sum"), 클릭=("클릭", "sum"))
            trend["CTR"] = trend["클릭"] / trend["노출"]
            fig = px.line(trend, x="일", y="CTR", color="소재", markers=True,
                          color_discrete_sequence=MUTED_PALETTE)
            st.plotly_chart(style_fig(fig), use_container_width=True)

    st.write("")

    with st.container(border=True):
        st.subheader("소재(크리에이티브)별 성과")
        by_creative = df.groupby(["채널", "소재"], as_index=False).agg(
            노출=("노출", "sum"), 클릭=("클릭", "sum"), 비용=("비용", "sum"),
            구매=("구매", "sum"), 구매매출=("구매매출", "sum"),
        )
        by_creative["CTR"] = by_creative["클릭"] / by_creative["노출"]
        by_creative["ROAS"] = by_creative["구매매출"] / by_creative["비용"]
        styled = by_creative.sort_values("구매매출", ascending=False).style.format({
            "노출": "{:,.0f}", "클릭": "{:,.0f}", "비용": "{:,.0f}원",
            "구매": "{:,.0f}", "구매매출": "{:,.0f}원", "CTR": "{:.2%}", "ROAS": "{:.1%}",
        })
        st.dataframe(styled, use_container_width=True, hide_index=True)

# ================= 탭 4: 이상탐지·데이터품질 =================
with tab_quality:
    with st.container(border=True):
        st.subheader("조인 상태")
        if len(unmatched) > 0:
            st.warning(f"조인 키(일/채널/캠페인/그룹/소재)가 매칭되지 않은 행이 {len(unmatched)}건 있습니다.")
            st.dataframe(unmatched, use_container_width=True)
        else:
            st.success("모든 행이 정상적으로 조인되었습니다.")

    st.write("")

    with st.container(border=True):
        st.subheader("KPI 임계값 알림 설정")
        if ROAS_ALERT_MIN is None and CPA_ALERT_MAX is None:
            st.caption("⚠ 아직 임계값이 설정되지 않았습니다. `dashboard.py` 상단의 "
                        "`ROAS_ALERT_MIN` / `CPA_ALERT_MAX`와 `raw_data/NAMING_CONVENTION.md`의 "
                        "'KPI 임계값' 항목을 함께 채워주세요.")
        else:
            st.write(f"ROAS 하한선: {ROAS_ALERT_MIN}, CPA 상한선: {CPA_ALERT_MAX}")

    st.write("")

    with st.expander("조인 원본 데이터 보기"):
        st.dataframe(df, use_container_width=True)
