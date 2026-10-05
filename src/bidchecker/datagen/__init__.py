"""合成数据生成器：固定 seed 产出招标/投标文件 + 真值 + 缺陷注入（plan/05 §一）。

核心资产：真值语义（主期望 + also_expect 全集合对账）与互斥坑记录必须写在本包
模块注释里（M1 交付）。CLI：bidchecker datagen。
"""
