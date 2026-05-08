#!/bin/bash
# 调整地震目录列顺序为: Year Month Day Hour Minute Second Lon Lat Mag Dep

# ChangningRelocation_YiGuixi.dat: Year Month Day Hour Minute Second Lat Lon Mag Dep → 交换第7、8列
awk '{t=$7; $7=$8; $8=t; print}' D:/study/program/seismicitymigration/seismig2d-v4/data/ChangningRelocation_YiGuixi.dat > D:/study/claude/tmp/ChangningRelocation_YiGuixi_fixed.txt

# Changning_AI_relo.txt: Year Month Day Hour Minute Second Lat Lon Mag Dep → 交换第7、8列
awk '{t=$7; $7=$8; $8=t; print}' D:/study/program/seismicitymigration/seismig2d-v4/data/Changning_AI_relo.txt > D:/study/claude/tmp/Changning_AI_relo_fixed.txt

# DataS1_noXYZ2.txt: Year Month Day Hour Minute Second Lat Lon Mag Dep → 交换第7、8列
awk '{t=$7; $7=$8; $8=t; print}' D:/study/program/seismicitymigration/seismig2d-v4/data/DataS1_noXYZ2.txt > D:/study/claude/tmp/DataS1_noXYZ2_fixed.txt

# wenchuan_eq_relocation_HuangWuFang.txt: 有表头，数据列: Year Month Day Hour Minute Second Mag Lat Lon Dep → 重排
tail -n +2 D:/study/program/seismicitymigration/seismig2d-v4/data/wenchuan_eq_relocation_HuangWuFang.txt | awk '{print $1, $2, $3, $4, $5, $6, $9, $8, $7, $10}' > D:/study/claude/tmp/wenchuan_HuangWuFang_fixed.txt

# wenchuan_eq_relocation_HuangWuFang_7days.txt: 同上
tail -n +2 D:/study/program/seismicitymigration/seismig2d-v4/data/wenchuan_eq_relocation_HuangWuFang_7days.txt | awk '{print $1, $2, $3, $4, $5, $6, $9, $8, $7, $10}' > D:/study/claude/tmp/wenchuan_HuangWuFang_7days_fixed.txt

echo "转换完成"
