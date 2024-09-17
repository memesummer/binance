#!/bin/bash

# 使用指定的时区来执行任务
export TZ='UTC'
export PATH=/usr/local/bin:/usr/bin:/bin

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
nohup python -u binance_bot.py > bot.log 2>&1 &
nohup python -u binance_recommed.py > push.log 2>&1 &
nohup python -u scan_big_order.py > scan.log 2>&1 &

echo "程序已重新启动"
