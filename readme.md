

```shell script
#打包
docker build -t registry.onlybox.cn/switches-quest:1.5 .
#运行
提前放置好sqlite数据库
docker run -d --name switches.keyboard -p 8002:8002 \
  -v /home/switches.keyboard/content:/usr/main/content
  switches.keyboard
```

```shell script
registry.cn-hangzhou.aliyuncs.com/hotcherry/switches.keyboard
docker build -t registry.cn-hangzhou.aliyuncs.com/crow1024/switches.keyboard:1 .
```