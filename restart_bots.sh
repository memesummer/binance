#!/bin/bash

# 使用指定的时区来执行任务
export TZ='UTC'
export PATH=/opt/anaconda3/envs/bot/bin:/usr/local/bin:/usr/bin:/bin


source /opt/anaconda3/bin/activate bot

echo "开始执行脚本: $(date)" >> /opt/daixin/binance/restart_bots.log
echo "环境变量 PATH: $PATH" >> /opt/daixin/binance/restart_bots.log
echo "环境变量 PYTHONPATH: $PYTHONPATH" >> /opt/daixin/binance/restart_bots.log
echo "当前工作目录: $(pwd)" >> /opt/daixin/binance/restart_bots.log
echo "当前 Python 解释器路径: $(which python)" >> /opt/daixin/binance/restart_bots.log
echo "当前 Conda 环境: $(conda info --envs)" >> /opt/daixin/binance/restart_bots.log


# 获取进程 ID 并杀掉相应的程序
pids=$(ps aux | grep -E 'binance_bot.py|binance_recommed.py|scan_big_order.py' | grep -v grep | awk '{print $2}')

if [ -n "$pids" ]; then
  echo "正在停止运行的程序: $pids"
  kill -9 $pids
else
  echo "没有找到要停止的程序"
fi

# 等待几秒以确保进程完全终止
sleep 5

# 重新启动程序
echo "正在重新启动程序..."
/usr/bin/nohup /opt/anaconda3/envs/bot/bin/python -u /opt/daixin/binance/binance_bot.py > bot.log 2>&1 &
sleep 1
/usr/bin/nohup /opt/anaconda3/envs/bot/bin/python -u /opt/daixin/binance/binance_recommed.py > push.log 2>&1 &
sleep 1
/usr/bin/nohup /opt/anaconda3/envs/bot/bin/python -u /opt/daixin/binance/scan_big_order.py > scan.log 2>&1 &

echo "程序已重新启动"
