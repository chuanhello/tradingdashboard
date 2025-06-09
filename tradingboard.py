
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import threading
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# 导入原有的交易机器人模块
# 注意：在实际使用时，需要将uso_bollinger_trading_bot.py放在同一目录下
try:
    from uso_bollinger_trading_bot import USO_TradingBot, BollingerBandsStrategy, NotificationManager
except ImportError:
    st.error("請確認uso_bollinger_trading_bot.py文件在同一目錄下")

# 页面配置
st.set_page_config(
    page_title="USO布林帶交易監控系統",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-container {
        background: linear-gradient(90deg, #f0f2f6, #ffffff);
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .status-running {
        color: #28a745;
        font-weight: bold;
    }
    .status-stopped {
        color: #dc3545;
        font-weight: bold;
    }
    .signal-alert {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

class StreamlitTradingInterface:
    def __init__(self):
        self.bot = None
        self.monitoring_active = False
        self.data_placeholder = st.empty()

        # 初始化session state
        if 'bot_running' not in st.session_state:
            st.session_state.bot_running = False
        if 'signals_history' not in st.session_state:
            st.session_state.signals_history = []
        if 'last_update' not in st.session_state:
            st.session_state.last_update = None

    def create_sidebar_controls(self):
        """创建侧边栏控制面板"""
        st.sidebar.markdown("## 📊 交易監控控制台")

        # 交易参数设置
        st.sidebar.markdown("### 策略参数")
        symbol = st.sidebar.text_input("交易標的", value="USO", help="輸入股票代碼")
        period = st.sidebar.slider("移動平均週期", 10, 50, 20, help="布林帶計算的移動平均天數")
        std_dev = st.sidebar.slider("標準差倍數", 1.0, 3.0, 2.0, 0.1, help="布林帶寬度的標準差倍數")
        check_interval = st.sidebar.slider("檢查間隔(秒)", 10, 300, 30, help="監控數據的時間間隔")

        # 监控控制按钮
        st.sidebar.markdown("### 監控控制")
        col1, col2 = st.sidebar.columns(2)

        with col1:
            if st.button("🚀 開始監控", disabled=st.session_state.bot_running):
                self.start_monitoring(symbol, period, std_dev, check_interval)

        with col2:
            if st.button("⏹️ 停止監控", disabled=not st.session_state.bot_running):
                self.stop_monitoring()

        # 显示当前状态
        status = "運行中" if st.session_state.bot_running else "已停止"
        status_class = "status-running" if st.session_state.bot_running else "status-stopped"
        st.sidebar.markdown(f"**監控狀態:** <span class='{status_class}'>{status}</span>", unsafe_allow_html=True)

        if st.session_state.last_update:
            st.sidebar.markdown(f"**最後更新:** {st.session_state.last_update}")

        # 通知设置
        st.sidebar.markdown("### 📧 通知设置")
        email_enabled = st.sidebar.checkbox("啟用郵件通知")
        sound_enabled = st.sidebar.checkbox("啟用聲音提醒", value=True)

        if email_enabled:
            email_config = {
                "sender_email": st.sidebar.text_input("發送信件"),
                "sender_password": st.sidebar.text_input("郵箱密碼", type="password"),
                "recipient_email": st.sidebar.text_input("接收郵箱")
            }

            if st.sidebar.button("保存郵件設置"):
                self.save_notification_config(email_config, sound_enabled)
                st.sidebar.success("郵件設置已保存")

        return symbol, period, std_dev, check_interval

    def save_notification_config(self, email_config, sound_enabled):
        """保存通知配置"""
        config = {
            "email": {
                "enabled": True,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                **email_config
            },
            "console": {"enabled": True},
            "sound": {"enabled": sound_enabled}
        }

        with open("notification_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def start_monitoring(self, symbol, period, std_dev, check_interval):
        """开始监控"""
        try:
            self.bot = USO_TradingBot(symbol=symbol, check_interval=check_interval)
            self.bot.strategy.period = period
            self.bot.strategy.std_dev = std_dev

            st.session_state.bot_running = True
            st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.sidebar.success(f"開始監控 {symbol}")

        except Exception as e:
            st.sidebar.error(f"啟動監控失敗: {e}")

    def stop_monitoring(self):
        """停止监控"""
        if self.bot:
            self.bot.is_running = False
            st.session_state.bot_running = False
            st.sidebar.success("監控已停止")

    def fetch_and_display_data(self, symbol, period, std_dev):
        """获取并显示市场数据"""
        try:
            # 创建策略实例
            strategy = BollingerBandsStrategy(symbol=symbol, period=period, std_dev=std_dev)

            # 获取市场数据
            data = strategy.fetch_market_data()
            if data is None:
                st.error("無法獲取市場數據")
                return None

            # 计算布林带
            data = strategy.calculate_bollinger_bands(data)

            # 获取当前状态
            status = strategy.get_current_status(data)

            # 检测信号
            signal = strategy.detect_buy_signal(data)
            if signal:
                st.session_state.signals_history.append(signal)

            return data, status, signal

        except Exception as e:
            st.error(f"數據處理錯誤: {e}")
            return None

    def create_bollinger_chart(self, data, symbol):
        """创建布林带图表"""

        if data is None or len(data) < 20:
            st.warning("數據不足，無法繪製圖表")
            return

        # 创建子图
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=(f'{symbol} 價格布林帶', '成交量'),
            row_heights=[0.7, 0.3]
        )

        # 主图：K线和布林带
        fig.add_trace(
            go.Candlestick(
                x=data.index,
                open=data['Open'],
                high=data['High'],
                low=data['Low'],
                close=data['Close'],
                name='價格',
                increasing_line_color='#26a69a',
                decreasing_line_color='#ef5350'
            ),
            row=1, col=1
        )

        # 布林带上轨
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data['Upper_Band'],
                mode='lines',
                name='上軌',
                line=dict(color='red', width=1),
                fill=None
            ),
            row=1, col=1
        )

        # 布林带中轨（移动平均线）
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data['SMA'],
                mode='lines',
                name='中軌(SMA)',
                line=dict(color='orange', width=2)
            ),
            row=1, col=1
        )

        # 布林带下轨
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data['Lower_Band'],
                mode='lines',
                name='下軌',
                line=dict(color='red', width=1),
                fill='tonexty',
                fillcolor='rgba(255,0,0,0.1)'
            ),
            row=1, col=1
        )
        print(data['Volume'])
        # 成交量图
        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data['Volume'].astype(int),
                name='成交量',
                marker_color='lightblue',
                opacity=0.7
            ),
            row=2, col=1
        )
        # 更新布局
        fig.update_layout(
            title=f'{symbol} 布林帶策略分析',
            xaxis_title='日期',
            yaxis_title='價格 ($)',
            height=700,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            template='plotly_white',
            xaxis=dict(
                type='category',  # 設定為類別型，這樣就不會顯示缺失的日期
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            xaxis2=dict(
                type='category',  # 第二個子圖的 x 軸也要設定
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            yaxis=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.2)'
            ),
            yaxis2=dict(
                showgrid=True,
                gridwidth=1,
                gridcolor='rgba(128,128,128,0.2)'
            )
        )

        return fig

    def display_current_status(self, status):
        """显示当前市场状态"""
        if not status:
            return

        st.markdown("### 📊 實時市場狀態")

        # 创建指标显示
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                label="當前價格",
                value=f"${float(status['current_price']):.2f}",
                delta=None
            )

        with col2:
            if status.get('upper_band'):
                st.metric(
                    label="上軌",
                    value=f"${status['upper_band']:.2f}"
                )

        with col3:
            if status.get('middle_band'):
                st.metric(
                    label="中軌",
                    value=f"${status['middle_band']:.2f}"
                )

        with col4:
            if status.get('lower_band'):
                st.metric(
                    label="下軌",
                    value=f"${status['lower_band']:.2f}"
                )

        # 价格位置分析
        if status.get('position'):
            st.info(f"**價格位置分析:** {status['position']}")

        if status.get('percent_b') is not None:
            percentage = status['percent_b'] * 100
            st.progress(min(max(percentage/100, 0), 1))
            st.caption(f"%B指标: {percentage:.1f}%")

    def display_signals_history(self):
        """显示信号历史"""
        st.markdown("### 🚨 交易訊號歷史")

        if not st.session_state.signals_history:
            st.info("暫無交易訊號")
            return

        # 转换信号历史为DataFrame
        signals_data = []
        for signal in st.session_state.signals_history:
            signals_data.append({
                '時間': signal.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                '標的': signal.symbol,
                '訊號類型': signal.signal_type,
                '觸發價格': f"${signal.price:.2f}",
                '上軌': f"${signal.upper_band:.2f}",
                '中軌': f"${signal.middle_band:.2f}",
                '下軌': f"${signal.lower_band:.2f}",
                '描述': signal.message
            })

        df_signals = pd.DataFrame(signals_data)
        st.dataframe(df_signals, use_container_width=True)

        # 最新信号提醒
        if signals_data:
            latest_signal = signals_data[-1]
            st.markdown(f"""
            <div class="signal-alert">
                <strong>🚨 最新訊號:</strong> {latest_signal['訊號類型']} | 
                <strong>價格:</strong> {latest_signal['觸發價格']} | 
                <strong>時間:</strong> {latest_signal['時間']}
            </div>
            """, unsafe_allow_html=True)

    def run(self):
        """运行主界面"""
        # 主标题
        st.markdown('<h1 class="main-header">🤖 USO布林帶交易監控系統</h1>', unsafe_allow_html=True)

        # 侧边栏控制
        symbol, period, std_dev, check_interval = self.create_sidebar_controls()

        # 主内容区域
        if st.session_state.bot_running:
            # 实时监控模式
            st.markdown("### 🔄 實時監控模式")

            # 创建占位符
            chart_placeholder = st.empty()
            status_placeholder = st.empty()
            signals_placeholder = st.empty()

            # 自动刷新数据
            if st.button("🔄 手動更新"):
                st.experimental_rerun()

            # 获取和显示数据
            result = self.fetch_and_display_data(symbol, period, std_dev)
            if result:
                data, status, signal = result

                with chart_placeholder.container():
                    chart = self.create_bollinger_chart(data, symbol)
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)

                with status_placeholder.container():
                    self.display_current_status(status)

                with signals_placeholder.container():
                    self.display_signals_history()

                # 更新最后更新时间
                st.session_state.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        else:
            # 静态模式
            st.markdown("### 📈 數據預覽模式")
            st.info("點擊側邊欄的'開始監控'按鈕啟動實時監控")

            # 显示样本数据
            if st.button("🔍 獲取當前數據"):
                result = self.fetch_and_display_data(symbol, period, std_dev)
                if result:
                    data, status, signal = result

                    chart = self.create_bollinger_chart(data, symbol)
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)

                    self.display_current_status(status)

        # 页脚信息
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #666666; font-size: 0.9rem;'>
            <p>📈 USO布林帶交易監控系統 | 基于Streamlit開發</p>
        </div>
        """, unsafe_allow_html=True)

# 运行应用
if __name__ == "__main__":
    app = StreamlitTradingInterface()
    app.run()
