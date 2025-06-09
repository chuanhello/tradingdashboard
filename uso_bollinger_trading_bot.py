# USO石油ETF布林帶交易機器人
# 技術分析：布林帶策略 (20日SMA, 2倍標準差)
# 買進訊號：收盤價從上往下穿越布林帶下軌

import pandas as pd
import numpy as np
import yfinance as yf
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging
import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, List
import warnings
import requests
warnings.filterwarnings('ignore')

@dataclass
class TradingSignal:
    """交易訊號資料結構"""
    timestamp: datetime
    symbol: str
    signal_type: str
    price: float
    upper_band: float
    middle_band: float
    lower_band: float
    message: str

class BollingerBandsStrategy:
    """布林帶交易策略類別"""
    
    def __init__(self, symbol: str = "USO", period: int = 20, std_dev: float = 2.0):
        self.symbol = symbol
        self.period = period
        self.std_dev = std_dev
        self.signals_history: List[TradingSignal] = []
        
        # 設定日誌
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'{symbol}_trading_log.txt'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def fetch_market_data(self, days: int = 60) -> Optional[pd.DataFrame]:
        """
        獲取市場資料
        
        Args:
            days: 獲取的歷史資料天數
            
        Returns:
            包含OHLCV資料的DataFrame，如果失敗則返回None
        """
        try:
            url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={self.symbol}&interval=1day&apikey=HHTX99VMKPOTXD8A'
            r = requests.get(url)
            data = r.json()
            data = pd.DataFrame(data['Time Series (Daily)']).T[::-1]
            data = data.rename(columns={'1. open': 'Open', '2. high': 'High', '3. low': 'Low', '4. close': 'Close', '5. volume': 'Volume'})

            if data.empty:
                self.logger.error(f"無法獲取 {self.symbol} 的資料")
                return None
                
            self.logger.info(f"成功獲取 {self.symbol} 最近 {len(data)} 天的資料")
            return data
            
        except Exception as e:
            self.logger.error(f"獲取市場資料時發生錯誤: {e}")
            return None
        '''
        try:
            # 使用yfinance獲取資料
            ticker = yf.Ticker(self.symbol)
            
            # 獲取歷史資料
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            data = ticker.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1d'
            )
            
            if data.empty:
                self.logger.error(f"無法獲取 {self.symbol} 的資料")
                return None
                
            self.logger.info(f"成功獲取 {self.symbol} 最近 {len(data)} 天的資料")
            return data
            
        except Exception as e:
            self.logger.error(f"獲取市場資料時發生錯誤: {e}")
            return None
        '''
    
    def calculate_bollinger_bands(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        計算布林帶指標
        
        Args:
            data: 包含價格資料的DataFrame
            
        Returns:
            包含布林帶指標的DataFrame
        """
        try:
            # 計算簡單移動平均（中軌）
            data['SMA'] = data['Close'].rolling(window=self.period).mean()
            
            # 計算標準差
            data['STD'] = data['Close'].rolling(window=self.period).std()
            
            # 計算上軌和下軌
            data['Upper_Band'] = data['SMA'] + (data['STD'] * self.std_dev)
            data['Lower_Band'] = data['SMA'] - (data['STD'] * self.std_dev)
            
            # 計算布林帶寬度（用於判斷波動性）
            data['BB_Width'] = data['Upper_Band'] - data['Lower_Band']
            
            # 計算價格相對位置 %B
            data['Percent_B'] = (data['Close'] - data['Lower_Band']) / (data['Upper_Band'] - data['Lower_Band'])
            
            self.logger.info("布林帶指標計算完成")
            return data
            
        except Exception as e:
            self.logger.error(f"計算布林帶指標時發生錯誤: {e}")
            return data
    
    def detect_buy_signal(self, data: pd.DataFrame) -> Optional[TradingSignal]:
        """
        檢測買進訊號：收盤價從上往下穿越布林帶下軌
        
        Args:
            data: 包含價格和布林帶資料的DataFrame
            
        Returns:
            TradingSignal物件或None
        """
        try:
            if len(data) < 2:
                return None
                
            # 獲取最近兩日的資料
            current = data.iloc[-1]
            previous = data.iloc[-2]
            
            # 檢查資料完整性
            required_columns = ['Close', 'Upper_Band', 'SMA', 'Lower_Band']
            if any(pd.isna(current[col]) or pd.isna(previous[col]) for col in required_columns):
                return None
            
            # 買進訊號條件：
            # 1. 前一日收盤價 >= 下軌（價格在下軌之上）
            # 2. 當日收盤價 < 下軌（價格跌破下軌）
            signal_triggered = (
                previous['Close'] >= previous['Lower_Band'] and 
                current['Close'] < current['Lower_Band']
            )
            
            if signal_triggered:
                signal = TradingSignal(
                    timestamp=datetime.now(),
                    symbol=self.symbol,
                    signal_type="BUY",
                    price=current['Close'],
                    upper_band=current['Upper_Band'],
                    middle_band=current['SMA'],
                    lower_band=current['Lower_Band'],
                    message=f"{self.symbol} 觸發買進訊號！收盤價 ${current['Close']:.2f} 跌破下軌 ${current['Lower_Band']:.2f}"
                )
                
                self.signals_history.append(signal)
                self.logger.info(f"🚨 買進訊號觸發: {signal.message}")
                return signal
                
            return None
            
        except Exception as e:
            self.logger.error(f"檢測買進訊號時發生錯誤: {e}")
            return None
    
    def get_current_status(self, data: pd.DataFrame) -> Dict:
        """
        獲取當前市場狀態
        
        Args:
            data: 市場資料DataFrame
            
        Returns:
            包含當前狀態的字典
        """
        try:
            if data.empty:
                return {}
                
            current = data.iloc[-1]
            
            status = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': self.symbol,
                'current_price': current['Close'],
                'upper_band': current.get('Upper_Band', None),
                'middle_band': current.get('SMA', None),
                'lower_band': current.get('Lower_Band', None),
                'percent_b': current.get('Percent_B', None),
                'bb_width': current.get('BB_Width', None),
                'volume': current.get('Volume', None)
            }
            
            # 判斷當前價格位置
            if status['percent_b'] is not None:
                if status['percent_b'] > 1:
                    status['position'] = "上軌之上（可能超買）"
                elif status['percent_b'] > 0.8:
                    status['position'] = "接近上軌"
                elif status['percent_b'] > 0.2:
                    status['position'] = "中軌附近"
                elif status['percent_b'] > 0:
                    status['position'] = "接近下軌"
                else:
                    status['position'] = "下軌之下（可能超賣）"
            
            return status
            
        except Exception as e:
            self.logger.error(f"獲取當前狀態時發生錯誤: {e}")
            return {}

class NotificationManager:
    """通知管理器"""
    
    def __init__(self, config_file: str = "notification_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
        
    def load_config(self) -> Dict:
        """載入通知設定"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 預設設定
                default_config = {
                    "email": {
                        "enabled": False,
                        "smtp_server": "smtp.gmail.com",
                        "smtp_port": 587,
                        "sender_email": "",
                        "sender_password": "",
                        "recipient_email": ""
                    },
                    "console": {
                        "enabled": True
                    },
                    "sound": {
                        "enabled": True
                    }
                }
                self.save_config(default_config)
                return default_config
        except Exception as e:
            print(f"載入通知設定時發生錯誤: {e}")
            return {}
    
    def save_config(self, config: Dict):
        """儲存通知設定"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"儲存通知設定時發生錯誤: {e}")
    
    def send_email_notification(self, signal: TradingSignal):
        """發送電子郵件通知"""
        try:
            if not self.config.get("email", {}).get("enabled", False):
                return
                
            email_config = self.config["email"]
            
            # 建立郵件內容
            subject = f"🚨 {signal.symbol} 交易訊號通知"
            
            body = f"""
交易訊號詳情：

標的代碼：{signal.symbol}
訊號類型：{signal.signal_type}
觸發時間：{signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
當前價格：${signal.price:.2f}

布林帶資訊：
上軌：${signal.upper_band:.2f}
中軌：${signal.middle_band:.2f}
下軌：${signal.lower_band:.2f}

訊號描述：
{signal.message}

---
此訊息由USO布林帶交易機器人自動發送
            """
            
            # 建立郵件
            msg = MIMEMultipart()
            msg['From'] = email_config["sender_email"]
            msg['To'] = email_config["recipient_email"]
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # 發送郵件
            server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
            server.starttls()
            server.login(email_config["sender_email"], email_config["sender_password"])
            
            text = msg.as_string()
            server.sendmail(email_config["sender_email"], email_config["recipient_email"], text)
            server.quit()
            
            print("✅ 電子郵件通知已發送")
            
        except Exception as e:
            print(f"❌ 發送電子郵件時發生錯誤: {e}")
    
    def send_console_notification(self, signal: TradingSignal):
        """發送控制台通知"""
        try:
            if not self.config.get("console", {}).get("enabled", True):
                return
                
            print("\n" + "="*60)
            print(f"🚨 {signal.signal_type} 訊號觸發！")
            print("="*60)
            print(f"標的代碼: {signal.symbol}")
            print(f"時間: {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"價格: ${signal.price:.2f}")
            print(f"上軌: ${signal.upper_band:.2f}")
            print(f"中軌: ${signal.middle_band:.2f}")
            print(f"下軌: ${signal.lower_band:.2f}")
            print(f"訊息: {signal.message}")
            print("="*60)
            
        except Exception as e:
            print(f"❌ 發送控制台通知時發生錯誤: {e}")
    
    def send_sound_notification(self, signal: TradingSignal):
        """發送聲音通知"""
        try:
            if not self.config.get("sound", {}).get("enabled", True):
                return
                
            # 在支援的系統上播放提示音
            try:
                import winsound
                winsound.Beep(1000, 500)  # 頻率1000Hz，持續500毫秒
            except ImportError:
                try:
                    import os
                    os.system('say "Trading signal triggered"')  # macOS
                except:
                    print("🔊 交易訊號提示音")  # 備用文字提示
                    
        except Exception as e:
            print(f"❌ 播放提示音時發生錯誤: {e}")
    
    def notify(self, signal: TradingSignal):
        """發送所有類型的通知"""
        self.send_console_notification(signal)
        self.send_email_notification(signal)
        self.send_sound_notification(signal)

class USO_TradingBot:
    """USO交易機器人主類別"""
    
    def __init__(self, symbol: str = "USO", check_interval: int = 30):
        self.symbol = symbol
        self.check_interval = check_interval  # 檢查間隔（秒）
        self.strategy = BollingerBandsStrategy(symbol)
        self.notification_manager = NotificationManager()
        self.is_running = False
        
        # 設定日誌
        self.logger = logging.getLogger(__name__)
        
    def print_current_status(self, status: Dict):
        """顯示當前狀態"""
        if not status:
            return
            
        print(f"\n📊 {status['timestamp']} - {status['symbol']} 當前狀態:")
        print(f"   當前價格: ${status['current_price']:.2f}")
        
        if status.get('upper_band'):
            print(f"   布林帶上軌: ${status['upper_band']:.2f}")
            print(f"   布林帶中軌: ${status['middle_band']:.2f}")
            print(f"   布林帶下軌: ${status['lower_band']:.2f}")
            
        if status.get('position'):
            print(f"   價格位置: {status['position']}")
            
        if status.get('percent_b') is not None:
            print(f"   %B指標: {status['percent_b']:.3f}")
    
    def run_single_check(self):
        """執行單次檢查"""
        try:
            # 獲取市場資料
            data = self.strategy.fetch_market_data()
            if data is None:
                self.logger.error("無法獲取市場資料")
                return
            
            # 計算布林帶
            data = self.strategy.calculate_bollinger_bands(data)
            
            # 獲取當前狀態
            status = self.strategy.get_current_status(data)
            self.print_current_status(status)
            
            # 檢測交易訊號
            signal = self.strategy.detect_buy_signal(data)
            if signal:
                self.notification_manager.notify(signal)
                
        except Exception as e:
            self.logger.error(f"執行檢查時發生錯誤: {e}")
    
    def start_monitoring(self):
        """開始監控"""
        print(f"🤖 USO布林帶交易機器人啟動")
        print(f"📈 監控標的: {self.symbol}")
        print(f"⏰ 檢查間隔: {self.check_interval}秒")
        print(f"📋 策略參數: {self.strategy.period}日SMA, {self.strategy.std_dev}倍標準差")
        print("按 Ctrl+C 停止監控...")
        
        self.is_running = True
        
        try:
            while self.is_running:
                self.run_single_check()
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n⏹️ 監控已停止")
            self.is_running = False
        except Exception as e:
            self.logger.error(f"監控過程中發生錯誤: {e}")
            self.is_running = False
    
    def get_signals_history(self) -> List[TradingSignal]:
        """取得歷史訊號"""
        return self.strategy.signals_history
    
    def save_signals_to_csv(self, filename: str = None):
        """將訊號歷史儲存到CSV檔案"""
        if not filename:
            filename = f"{self.symbol}_signals_{datetime.now().strftime('%Y%m%d')}.csv"
            
        try:
            signals_data = []
            for signal in self.strategy.signals_history:
                signals_data.append({
                    'timestamp': signal.timestamp,
                    'symbol': signal.symbol,
                    'signal_type': signal.signal_type,
                    'price': signal.price,
                    'upper_band': signal.upper_band,
                    'middle_band': signal.middle_band,
                    'lower_band': signal.lower_band,
                    'message': signal.message
                })
            
            df = pd.DataFrame(signals_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"✅ 訊號歷史已儲存到 {filename}")
            
        except Exception as e:
            print(f"❌ 儲存訊號歷史時發生錯誤: {e}")

def main():
    """主程式"""
    print("🚀 USO石油ETF布林帶交易機器人")
    print("=" * 50)
    
    # 創建交易機器人
    bot = USO_TradingBot(symbol="USO", check_interval=30)
    
    # 提供選擇
    print("請選擇運行模式:")
    print("1. 持續監控模式（每30秒檢查一次）")
    print("2. 單次檢查模式")
    print("3. 查看設定檔案位置")
    
    try:
        choice = input("請輸入選擇 (1/2/3): ").strip()
        
        if choice == "1":
            bot.start_monitoring()
        elif choice == "2":
            print("執行單次檢查...")
            bot.run_single_check()
        elif choice == "3":
            print(f"通知設定檔案: notification_config.json")
            print(f"交易日誌檔案: {bot.symbol}_trading_log.txt")
            print("您可以編輯 notification_config.json 來設定電子郵件通知")
        else:
            print("無效的選擇")
            
    except KeyboardInterrupt:
        print("\n程式已結束")
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    main()