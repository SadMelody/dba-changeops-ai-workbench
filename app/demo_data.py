from __future__ import annotations

from app.models import Case, DemoFixture


ARTIFACT_TITLES = {
    "risk_assessment": "风险评估",
    "runbook": "执行 Runbook",
    "rollback_plan": "回滚方案",
    "precheck_sql": "前置检查 SQL",
    "acceptance_checklist": "验收清单",
    "communication_summary": "变更沟通摘要",
}


DEMO_CASES = [
    {
        "slug": "db2-index-online",
        "old_title": "DB2 customer order slow query index change",
        "title": "DB2 客户订单慢查询索引变更",
        "db_type": "DB2 LUW",
        "target_system": "订单结算平台",
        "change_type": "在线创建索引",
        "priority": "P2",
        "environment": "生产",
        "owner": "DBA 值班负责人",
        "approver": "变更经理",
        "planned_window": "2026-06-03 23:00-00:30",
        "business_context": (
            "月度结算报表在高峰期频繁超时。运维希望通过在线索引变更改善查询，"
            "并要求方案包含可回滚的执行 Runbook。"
        ),
        "source_sql": (
            "CREATE INDEX IX_ORDERS_SETTLE_DATE_STATUS\n"
            "ON APP.ORDERS (SETTLE_DATE, STATUS)\n"
            "ALLOW REVERSE SCANS;\n"
        ),
        "schema_notes": (
            "APP.ORDERS 约 8500 万行。现有索引覆盖 ORDER_ID 和 CUSTOMER_ID。"
            "该表参与夜间 ETL 和月末报表。"
        ),
        "constraints": (
            "维护窗口：23:00-00:30。避免长时间排他锁。回滚动作需要控制在 10 分钟内。"
        ),
    },
    {
        "slug": "db2-add-column",
        "old_title": "DB2 add nullable channel column for payment audit",
        "title": "DB2 支付审计表新增可空渠道字段",
        "db_type": "DB2 z/OS",
        "target_system": "支付审计库",
        "change_type": "DDL 加字段",
        "priority": "P3",
        "environment": "生产",
        "owner": "支付 DBA",
        "approver": "支付应用负责人",
        "planned_window": "2026-06-05 22:30-23:30",
        "business_context": "审计服务需要记录支付渠道，用于下游对账和差异追踪。",
        "source_sql": "ALTER TABLE PAY.TXN_AUDIT ADD COLUMN CHANNEL_CD CHAR(4);\n",
        "schema_notes": "PAY.TXN_AUDIT 在业务时段写入量较高，涉及审计查询和对账批处理。",
        "constraints": "不允许应用停机。执行前需要确认 package rebind 要求。",
    },
    {
        "slug": "db2-data-fix",
        "old_title": "Correct duplicate customer risk flags",
        "title": "修正客户风险标识重复数据",
        "db_type": "DB2 LUW",
        "target_system": "客户风险平台",
        "change_type": "受控数据修复",
        "priority": "P1",
        "environment": "生产",
        "owner": "风险平台 DBA",
        "approver": "风控业务负责人",
        "planned_window": "2026-06-02 21:00-22:00",
        "business_context": "一次批处理缺陷导致 1,248 条客户记录出现重复风险标识，需要受控修复。",
        "source_sql": (
            "UPDATE RISK.CUSTOMER_FLAG\n"
            "SET ACTIVE_IND='N', UPDATED_BY='OPS_FIX_20260601'\n"
            "WHERE BATCH_ID='B20260531' AND DUPLICATE_IND='Y';\n"
        ),
        "schema_notes": "RISK.CUSTOMER_FLAG 存在审计触发器，并同步到分析侧。",
        "constraints": "需要前后计数、备份表、业务确认和审计留痕。",
    },
    {
        "slug": "db2-reorg",
        "old_title": "Plan DB2 table reorg after heavy purge",
        "title": "大批量清理后规划 DB2 表重组",
        "db_type": "DB2 LUW",
        "target_system": "贷款归档库",
        "change_type": "REORG/RUNSTATS 维护",
        "priority": "P2",
        "environment": "生产",
        "owner": "归档库 DBA",
        "approver": "数据平台负责人",
        "planned_window": "2026-06-08 00:00-04:30",
        "business_context": "历史数据清理后查询性能下降，存储空间也没有按预期回收。",
        "source_sql": "REORG TABLE ARCH.LOAN_EVENT;\nRUNSTATS ON TABLE ARCH.LOAN_EVENT WITH DISTRIBUTION AND DETAILED INDEXES ALL;\n",
        "schema_notes": "ARCH.LOAN_EVENT 约 2.3 亿行，包含 14 个索引。",
        "constraints": "只读报表必须在 06:00 前恢复。执行期间重点监控临时表空间。",
    },
    {
        "slug": "db2-lock-incident",
        "old_title": "Investigate repeated lock waits on account table",
        "title": "排查账户表反复锁等待问题",
        "db_type": "DB2 LUW",
        "target_system": "账户服务库",
        "change_type": "故障分析",
        "priority": "P1",
        "environment": "生产",
        "owner": "账户库 DBA",
        "approver": "应急变更指挥",
        "planned_window": "故障窗口内按应急流程执行",
        "business_context": "接口延迟尖峰与 ACCT.ACCOUNT_BALANCE 上的锁等待高度相关。",
        "source_sql": "SELECT * FROM SYSIBMADM.LOCKWAITS WHERE TABSCHEMA='ACCT';\n",
        "schema_notes": "ACCT.ACCOUNT_BALANCE 同时被联机交易和计息批处理更新。",
        "constraints": "未经批准不得直接 kill session。需要形成故障复盘证据包。",
    },
    {
        "slug": "db2-hadr-takeover",
        "old_title": "DB2 HADR controlled takeover rehearsal",
        "title": "DB2 HADR 受控切换演练",
        "db_type": "DB2 LUW HADR",
        "target_system": "核心账务库",
        "change_type": "HADR 受控切换",
        "priority": "P1",
        "environment": "生产",
        "owner": "核心库 DBA",
        "approver": "业务连续性负责人",
        "planned_window": "2026-06-10 01:00-02:00",
        "business_context": "为验证机房级容灾能力，需要在低峰窗口执行一次受控 HADR 主备切换演练。",
        "source_sql": (
            "db2pd -db COREDB -hadr\n"
            "TAKEOVER HADR ON DATABASE COREDB BY FORCE PEER WINDOW ONLY;\n"
        ),
        "schema_notes": "COREDB 运行在 HADR PEER 模式，应用通过 VIP 和连接池访问主库。",
        "constraints": "允许 5 分钟以内连接抖动。切换前必须确认日志差距、复制状态和应用重连策略。",
    },
    {
        "slug": "db2-tablespace-expand",
        "old_title": "DB2 tablespace capacity expansion",
        "title": "DB2 表空间容量扩容",
        "db_type": "DB2 LUW",
        "target_system": "交易流水库",
        "change_type": "表空间扩容",
        "priority": "P2",
        "environment": "生产",
        "owner": "交易库 DBA",
        "approver": "交易平台负责人",
        "planned_window": "2026-06-11 22:00-23:00",
        "business_context": "交易流水表空间使用率超过 88%，未来两周促销流量可能触发空间告警。",
        "source_sql": "ALTER TABLESPACE TS_TXN_DATA EXTEND (ALL 102400 M);\n",
        "schema_notes": "TS_TXN_DATA 使用 DMS 自动存储，承载 TXN.EVENT_LOG 和 TXN.PAYMENT_TRACE。",
        "constraints": "扩容期间不允许影响联机写入。需要确认文件系统、自动存储路径和备份窗口。",
    },
    {
        "slug": "db2-privilege-change",
        "old_title": "DB2 least privilege grant cleanup",
        "title": "DB2 报表账号最小权限调整",
        "db_type": "DB2 LUW",
        "target_system": "经营分析库",
        "change_type": "权限变更",
        "priority": "P3",
        "environment": "生产",
        "owner": "分析库 DBA",
        "approver": "数据安全负责人",
        "planned_window": "2026-06-12 20:00-21:00",
        "business_context": "安全审计发现报表账号拥有超出需要的写权限，需要收敛为只读访问。",
        "source_sql": (
            "REVOKE INSERT, UPDATE, DELETE ON TABLE BI.DAILY_REVENUE FROM USER BI_REPORT;\n"
            "GRANT SELECT ON TABLE BI.DAILY_REVENUE TO USER BI_REPORT;\n"
        ),
        "schema_notes": "BI_REPORT 被 12 个报表任务和 3 个临时分析脚本使用。",
        "constraints": "变更后必须验证核心报表可读，且不能保留多余写权限。需要数据安全复核。",
    },
]


def seed_demo_data(db) -> None:
    for item in DEMO_CASES:
        fixture = db.query(DemoFixture).filter(DemoFixture.slug == item["slug"]).first()
        if fixture:
            fixture.title = item["title"]
            fixture.payload = item
        else:
            db.add(DemoFixture(slug=item["slug"], title=item["title"], payload=item))

    for item in DEMO_CASES:
        titles = [item["title"], item.get("old_title", item["title"])]
        case = db.query(Case).filter(Case.title.in_(titles)).first()
        if not case:
            case = Case(status="draft")
            db.add(case)
        case.title = item["title"]
        case.db_type = item["db_type"]
        case.target_system = item["target_system"]
        case.change_type = item["change_type"]
        case.priority = item["priority"]
        case.environment = item["environment"]
        case.owner = item["owner"]
        case.approver = item["approver"]
        case.planned_window = item["planned_window"]
        case.business_context = item["business_context"]
        case.source_sql = item["source_sql"]
        case.schema_notes = item["schema_notes"]
        case.constraints = item["constraints"]

        localized = fixture_analysis(case)
        for run in case.runs:
            if run.provider == "fixture" or run.model == "offline-demo":
                run.summary = localized["summary"]
                for artifact in run.artifacts:
                    artifact.title = ARTIFACT_TITLES.get(artifact.artifact_type, artifact.title)
                    artifact.content = localized["artifacts"].get(
                        artifact.artifact_type, artifact.content
                    )
                for log in run.llm_logs:
                    log.response_payload = localized
    db.commit()


def _scenario_key(case: Case) -> str:
    text = f"{case.title} {case.change_type} {case.source_sql}".lower()
    if "hadr" in text or "takeover" in text or "受控切换" in text:
        return "hadr"
    if "tablespace" in text or "表空间" in text or "extend" in text:
        return "tablespace"
    if "grant" in text or "revoke" in text or "权限" in text:
        return "privilege"
    if "lock" in text or "锁等待" in text or "故障" in text:
        return "lock_incident"
    if "reorg" in text or "runstats" in text or "表重组" in text:
        return "reorg"
    if "数据修复" in text or text.strip().startswith("update") or " update " in text:
        return "data_fix"
    if "add column" in text or "加字段" in text or "新增可空" in text:
        return "add_column"
    if "create index" in text or "索引" in text:
        return "index"
    return "generic"


def _scenario_artifacts(case: Case, risk_level: str) -> dict[str, str]:
    scenario = _scenario_key(case)
    if scenario == "hadr":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 复制状态：切换前必须确认 HADR_STATE=PEER，日志差距和重放延迟均在阈值内。\n"
                "- 连接影响：应用 VIP、连接池和重连策略需要提前验证，避免切换后长时间连旧主库。\n"
                "- 数据一致性：禁止在非 PEER 或日志差距异常时执行强制切换，除非进入灾难恢复流程。\n"
                "- 监控窗口：切换前后持续观察主备角色、日志传输、交易错误率和连接数。\n"
                "- 回切边界：演练必须明确是否回切、回切窗口和业务验收标准。"
            ),
            "runbook": (
                "1. 宣布进入 HADR 受控切换演练，冻结数据库结构和批处理变更。\n"
                "2. 采集 db2pd -hadr、日志差距、VIP 状态、应用连接池和交易成功率基线。\n"
                "3. 确认主备均处于 PEER 状态，且业务负责人接受 5 分钟以内连接抖动。\n"
                "4. 执行已评审 TAKEOVER HADR 命令，并记录角色切换时间点。\n"
                "5. 验证新主库可写、旧主库进入备库角色、VIP 或连接入口已切到新主库。\n"
                "6. 观察 15 分钟交易成功率、连接错误、日志传输和告警。\n"
                "7. 汇总演练证据，确认是否按计划回切或保持新主库。"
            ),
            "rollback_plan": (
                "回滚触发条件：新主库不可写、应用无法重连、日志复制异常，"
                "或交易错误率超过演练阈值。\n\n"
                "- 立即停止后续回切或批处理恢复动作。\n"
                "- 根据当前 HADR 角色确认是否执行反向 TAKEOVER 或恢复原 VIP 指向。\n"
                "- 与应用负责人确认连接池重置、缓存刷新和交易重试状态。\n"
                "- 保存 db2pd -hadr、应用错误率、VIP 切换和角色状态证据。\n"
                "- 若进入灾难恢复模式，按业务连续性预案升级，不再按普通演练处理。"
            ),
            "precheck_sql": (
                "-- HADR 状态基线\n"
                "db2pd -db COREDB -hadr\n\n"
                "-- 数据库可写和连接验证\n"
                "VALUES CURRENT SERVER;\n"
                "SELECT COUNT(*) FROM SYSIBMADM.APPLICATIONS;\n\n"
                "-- 活跃事务和长事务观察\n"
                "SELECT * FROM SYSIBMADM.MON_CURRENT_UOW FETCH FIRST 30 ROWS ONLY;"
            ),
            "acceptance_checklist": (
                "- [ ] 切换前 HADR_STATE 为 PEER，日志差距在阈值内。\n"
                "- [ ] 新主库可读写，旧主库角色正确。\n"
                "- [ ] 应用连接入口已指向新主库，连接池恢复正常。\n"
                "- [ ] 交易成功率、错误率和延迟回到演练阈值内。\n"
                "- [ ] db2pd -hadr、VIP 状态和应用验证证据已归档。\n"
                "- [ ] 回切决策和后续观察责任人已确认。"
            ),
        }
    if scenario == "tablespace":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 容量风险：扩容前确认表空间、自动存储路径和文件系统剩余空间满足增长量。\n"
                "- 写入影响：交易流水库写入持续发生，需确认 ALTER TABLESPACE 不阻塞核心写入路径。\n"
                "- 备份影响：扩容后备份窗口和存储占用可能变化，需要提前通知备份负责人。\n"
                "- 告警联动：监控阈值、容量预测和自动扩展策略需同步更新。\n"
                "- 回退限制：表空间物理扩容通常不能简单缩回，错误扩容需以容量治理方式处理。"
            ),
            "runbook": (
                "1. 宣布表空间扩容开始，冻结同库大批量装载和清理任务。\n"
                "2. 采集 TBSP_UTILIZATION、自动存储路径、文件系统余量和备份窗口基线。\n"
                "3. 确认扩容量、目标表空间和审批记录一致。\n"
                "4. 执行 ALTER TABLESPACE EXTEND 语句。\n"
                "5. 扩容后立即复查表空间可用页、文件系统使用率和应用写入错误。\n"
                "6. 更新容量监控阈值和两周增长预测。\n"
                "7. 通知交易平台和备份负责人扩容完成。"
            ),
            "rollback_plan": (
                "回滚触发条件：扩容目标错误、文件系统空间异常下降，"
                "或扩容后写入链路出现持续错误。\n\n"
                "- 立即停止后续容量变更动作，保留 ALTER 执行记录。\n"
                "- 确认是否只是监控误报、自动存储路径异常或目标表空间选错。\n"
                "- 如目标错误，禁止继续写入依赖新空间的批量任务，并提交容量治理变更。\n"
                "- 如应用写入异常，优先恢复连接和表空间可用性，再处理空间回收。\n"
                "- 将扩容前后 TBSP_UTILIZATION 和文件系统证据归档。"
            ),
            "precheck_sql": (
                "-- 表空间使用率\n"
                "SELECT TBSP_NAME, TBSP_TYPE, TBSP_USED_PAGES, TBSP_FREE_PAGES, TBSP_PAGE_SIZE\n"
                "FROM SYSIBMADM.TBSP_UTILIZATION\n"
                "WHERE TBSP_NAME='TS_TXN_DATA';\n\n"
                "-- 表空间容器\n"
                "SELECT TBSP_NAME, CONTAINER_NAME, TOTAL_PAGES, USABLE_PAGES\n"
                "FROM SYSIBMADM.CONTAINER_UTILIZATION\n"
                "WHERE TBSP_NAME='TS_TXN_DATA';\n\n"
                "-- 目标业务表规模\n"
                "SELECT TABSCHEMA, TABNAME, CARD, NPAGES FROM SYSCAT.TABLES WHERE TABSCHEMA='TXN';"
            ),
            "acceptance_checklist": (
                "- [ ] TS_TXN_DATA 可用空间增加到审批目标。\n"
                "- [ ] 自动存储路径和文件系统空间仍在安全阈值内。\n"
                "- [ ] 联机写入无新增错误，交易流水持续入库。\n"
                "- [ ] 容量监控阈值和增长预测已更新。\n"
                "- [ ] 备份负责人确认扩容后备份窗口可接受。\n"
                "- [ ] 扩容 SQL、表空间截图和监控截图已归档。"
            ),
        }
    if scenario == "privilege":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 最小权限：必须确认 REVOKE 只移除写权限，不影响报表 SELECT 能力。\n"
                "- 依赖识别：报表任务、临时脚本和数据抽取账号需要提前核对实际使用权限。\n"
                "- 审计要求：权限调整要保留执行人、授权前后快照和数据安全审批。\n"
                "- 回退边界：如报表中断，只允许按审批恢复必要权限，避免恢复过宽授权。\n"
                "- 账号治理：变更后需要确认没有其他角色继续授予等价写权限。"
            ),
            "runbook": (
                "1. 宣布进入权限收敛窗口，确认数据安全审批编号。\n"
                "2. 采集 BI_REPORT 在目标表和角色上的授权快照。\n"
                "3. 与报表负责人确认 12 个任务和 3 个临时脚本不需要写权限。\n"
                "4. 执行 REVOKE INSERT/UPDATE/DELETE，并保留 SELECT 授权。\n"
                "5. 执行授权复查 SQL，确认写权限已移除且 SELECT 仍存在。\n"
                "6. 触发核心报表只读验证，观察任务错误和权限拒绝日志。\n"
                "7. 将授权前后快照和业务验证结论归档。"
            ),
            "rollback_plan": (
                "回滚触发条件：核心报表因权限调整失败，或存在经审批确认的必要写入任务。\n\n"
                "- 暂停进一步权限收敛动作，不恢复未审批的宽权限。\n"
                "- 只对被证明需要的对象和操作恢复最小授权。\n"
                "- 重新执行报表验证和授权快照，确认没有额外写权限。\n"
                "- 通知数据安全负责人更新例外清单和到期时间。\n"
                "- 记录失败任务、恢复授权语句和审批依据。"
            ),
            "precheck_sql": (
                "-- 表级授权快照\n"
                "SELECT GRANTEE, GRANTEETYPE, CONTROLAUTH, SELECTAUTH, INSERTAUTH, UPDATEAUTH, DELETEAUTH\n"
                "FROM SYSCAT.TABAUTH\n"
                "WHERE TABSCHEMA='BI' AND TABNAME='DAILY_REVENUE' AND GRANTEE='BI_REPORT';\n\n"
                "-- 角色授权检查\n"
                "SELECT * FROM SYSCAT.ROLEAUTH WHERE GRANTEE='BI_REPORT';\n\n"
                "-- 权限变更后应再次运行同样查询确认写权限为 N。"
            ),
            "acceptance_checklist": (
                "- [ ] BI_REPORT 的 INSERT/UPDATE/DELETE 权限已移除。\n"
                "- [ ] BI_REPORT 对 BI.DAILY_REVENUE 的 SELECT 权限仍可用。\n"
                "- [ ] 核心报表任务验证通过，无权限拒绝错误。\n"
                "- [ ] 角色授权没有绕过表级权限收敛。\n"
                "- [ ] 授权前后快照和数据安全审批已归档。\n"
                "- [ ] 如有例外权限，已记录到期时间和负责人。"
            ),
        }
    if scenario == "index":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 锁影响：确认 CREATE INDEX 方式不会在高峰期放大锁等待，必要时降低并发写入。\n"
                "- 访问计划：执行前保存关键 SQL 的 EXPLAIN，执行后确认优化器选择新增索引。\n"
                "- 统计信息：索引完成后安排 RUNSTATS，避免统计信息滞后导致计划不稳定。\n"
                "- 空间与日志：确认索引表空间、临时表空间和活动日志余量满足窗口要求。\n"
                "- 回滚窗口：预先准备 DROP INDEX，并确认 10 分钟内可完成回退。"
            ),
            "runbook": (
                "1. 宣布索引变更开始，冻结同表结构变更。\n"
                "2. 采集基线：LOCKWAITS、表空间、活动日志、关键 SQL 响应时间和 EXPLAIN。\n"
                "3. 确认夜间 ETL、月末报表和长事务均不在冲突窗口。\n"
                "4. 执行已评审 CREATE INDEX 语句。\n"
                "5. 每 3 分钟检查索引创建进度、锁等待、日志使用率和应用错误率。\n"
                "6. 索引创建完成后执行 RUNSTATS，并重新采集关键 SQL 访问计划。\n"
                "7. 验收响应时间和锁等待恢复情况，记录证据后宣布结束。"
            ),
            "rollback_plan": (
                "回滚触发条件：索引创建导致持续锁等待、日志使用率接近阈值，"
                "或关键交易错误率超过约定阈值。\n\n"
                "- 暂停后续统计信息动作，确认 CREATE INDEX 是否已完成。\n"
                "- 如果索引已创建，执行 DROP INDEX 删除新增索引。\n"
                "- 如已执行 RUNSTATS，重新采集基线并确认访问计划回到变更前水平。\n"
                "- 通知应用和批处理负责人恢复原执行路径观察。\n"
                "- 记录 DROP INDEX 时间点、锁等待恢复截图和最终影响范围。"
            ),
            "precheck_sql": (
                "-- 锁等待基线\n"
                "SELECT * FROM SYSIBMADM.LOCKWAITS WHERE TABSCHEMA='APP' FETCH FIRST 20 ROWS ONLY;\n\n"
                "-- 目标表统计信息\n"
                "SELECT TABSCHEMA, TABNAME, CARD, STATS_TIME\n"
                "FROM SYSCAT.TABLES\n"
                "WHERE TABSCHEMA='APP' AND TABNAME='ORDERS';\n\n"
                "-- 索引和表空间余量\n"
                "SELECT INDNAME, UNIQUERULE, STATS_TIME FROM SYSCAT.INDEXES WHERE TABSCHEMA='APP' AND TABNAME='ORDERS';\n"
                "SELECT TBSP_NAME, TBSP_USED_PAGES, TBSP_FREE_PAGES FROM SYSIBMADM.TBSP_UTILIZATION;"
            ),
            "acceptance_checklist": (
                "- [ ] 新索引在 SYSCAT.INDEXES 中可见。\n"
                "- [ ] RUNSTATS 已完成且 STATS_TIME 更新。\n"
                "- [ ] 关键 SQL EXPLAIN 选择新增索引或成本下降。\n"
                "- [ ] 关键报表响应时间达到业务验收阈值。\n"
                "- [ ] 未出现新增锁等待、日志告警或应用错误尖峰。\n"
                "- [ ] DROP INDEX 回滚语句已归档但未触发。"
            ),
        }
    if scenario == "data_fix":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 数据范围：必须用 WHERE 条件和预检查计数锁定 1,248 条目标记录。\n"
                "- 审计影响：确认触发器、复制链路和下游分析同步不会重复放大修复。\n"
                "- 备份要求：执行前创建受影响行备份表，并记录行数和校验摘要。\n"
                "- 事务控制：分批或单批提交策略需要与日志余量和锁影响匹配。\n"
                "- 业务复核：修复前后必须由风控业务负责人确认样本。"
            ),
            "runbook": (
                "1. 宣布进入受控数据修复窗口，确认业务审批编号。\n"
                "2. 执行 SELECT COUNT 预检查，确认影响范围与审批一致。\n"
                "3. 创建备份表保存目标记录，并校验备份行数。\n"
                "4. 执行已评审 UPDATE，记录开始时间、结束时间和影响行数。\n"
                "5. 立即执行修复后计数、抽样查询和审计触发器检查。\n"
                "6. 请业务负责人确认样本和汇总计数。\n"
                "7. 将备份表名、SQL、影响行数和业务确认截图归档。"
            ),
            "rollback_plan": (
                "回滚触发条件：UPDATE 影响行数不等于审批数量、抽样异常，"
                "或下游同步出现不可接受差异。\n\n"
                "- 立即停止后续修复动作并保留当前事务证据。\n"
                "- 使用备份表按主键恢复 ACTIVE_IND、UPDATED_BY 等被修改字段。\n"
                "- 对恢复结果执行前后计数和样本核验。\n"
                "- 通知风控业务负责人重新确认风险标识状态。\n"
                "- 保留原修复 SQL、回滚 SQL、备份表和所有计数证据。"
            ),
            "precheck_sql": (
                "-- 审批范围计数\n"
                "SELECT COUNT(*) AS TARGET_ROWS\n"
                "FROM RISK.CUSTOMER_FLAG\n"
                "WHERE BATCH_ID='B20260531' AND DUPLICATE_IND='Y';\n\n"
                "-- 执行前备份\n"
                "CREATE TABLE RISK.BAK_CUSTOMER_FLAG_20260602 AS\n"
                "(SELECT * FROM RISK.CUSTOMER_FLAG\n"
                " WHERE BATCH_ID='B20260531' AND DUPLICATE_IND='Y') WITH DATA;\n\n"
                "-- 备份校验\n"
                "SELECT COUNT(*) AS BACKUP_ROWS FROM RISK.BAK_CUSTOMER_FLAG_20260602;"
            ),
            "acceptance_checklist": (
                "- [ ] 预检查计数与变更审批数量一致。\n"
                "- [ ] 备份表已创建且行数一致。\n"
                "- [ ] UPDATE 影响行数与目标行数一致。\n"
                "- [ ] 修复后重复风险标识计数为 0 或符合业务预期。\n"
                "- [ ] 业务负责人完成样本复核。\n"
                "- [ ] 回滚 SQL 已验证可按备份表恢复。"
            ),
        }
    if scenario == "reorg":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 可用性：REORG 期间需确认访问模式，避免只读报表被阻塞到 06:00 之后。\n"
                "- 临时空间：重点确认系统临时表空间和目标表空间余量。\n"
                "- 统计信息：REORG 后必须 RUNSTATS，否则优化器可能继续使用旧统计。\n"
                "- 时长风险：2.3 亿行大表需要设置中止点和恢复策略。\n"
                "- 监控要求：执行期间持续观察 UTIL_HEAP、日志、I/O 和活动实用程序。"
            ),
            "runbook": (
                "1. 确认归档库只读报表窗口和 06:00 恢复要求。\n"
                "2. 采集表空间、临时表空间、表大小、索引数量和最近 RUNSTATS 时间。\n"
                "3. 暂停可能冲突的清理、装载和报表作业。\n"
                "4. 执行 REORG TABLE，并每 10 分钟记录实用程序进度。\n"
                "5. REORG 完成后立即执行 RUNSTATS WITH DISTRIBUTION AND DETAILED INDEXES ALL。\n"
                "6. 验证表空间回收、关键查询响应时间和报表连通性。\n"
                "7. 释放窗口并通知数据平台负责人。"
            ),
            "rollback_plan": (
                "回滚触发条件：REORG 进度无法在恢复窗口前完成、临时空间告警，"
                "或报表恢复时间存在风险。\n\n"
                "- 根据当前阶段判断是否中止 REORG 实用程序。\n"
                "- 保留表空间、实用程序状态和中止时间点证据。\n"
                "- 暂停 RUNSTATS，优先恢复只读报表可用性。\n"
                "- 如统计信息已更新但查询异常，执行指定版本统计恢复或重新 RUNSTATS。\n"
                "- 重新规划分区级或更长窗口维护。"
            ),
            "precheck_sql": (
                "-- 表和索引规模\n"
                "SELECT TABSCHEMA, TABNAME, CARD, NPAGES, FPAGES, STATS_TIME\n"
                "FROM SYSCAT.TABLES WHERE TABSCHEMA='ARCH' AND TABNAME='LOAN_EVENT';\n\n"
                "-- 活动实用程序\n"
                "SELECT * FROM SYSIBMADM.SNAPUTIL_PROGRESS FETCH FIRST 20 ROWS ONLY;\n\n"
                "-- 表空间和临时空间\n"
                "SELECT TBSP_NAME, TBSP_TYPE, TBSP_USED_PAGES, TBSP_FREE_PAGES\n"
                "FROM SYSIBMADM.TBSP_UTILIZATION;"
            ),
            "acceptance_checklist": (
                "- [ ] REORG 实用程序正常结束，无挂起状态。\n"
                "- [ ] RUNSTATS 完成且统计时间更新。\n"
                "- [ ] 表空间使用率或碎片情况达到维护预期。\n"
                "- [ ] 关键归档查询响应时间恢复或改善。\n"
                "- [ ] 06:00 前只读报表完成连通性验证。\n"
                "- [ ] 维护日志和实用程序进度截图已归档。"
            ),
        }
    if scenario == "lock_incident":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 处置边界：未经应急指挥批准不得直接 force application 或 kill session。\n"
                "- 证据优先：需要先采集锁持有者、等待者、SQL 文本、应用名和时间线。\n"
                "- 业务影响：账户余额表同时承载联机交易和计息批处理，误处置风险高。\n"
                "- 复盘要求：故障类案例必须形成原因、处置、恢复和预防项证据包。\n"
                "- 沟通节奏：每 10 分钟向应急群同步延迟、锁等待和处置建议。"
            ),
            "runbook": (
                "1. 宣布进入应急分析流程，指定记录人和决策人。\n"
                "2. 采集 LOCKWAITS、当前应用、活动 SQL、锁持有者和等待链。\n"
                "3. 判断锁源来自联机交易、计息批处理还是异常长事务。\n"
                "4. 与应用负责人确认是否允许暂停批处理或释放异常会话。\n"
                "5. 按批准动作执行限流、暂停批处理或会话处置。\n"
                "6. 每 5 分钟复查接口延迟、锁等待数量和错误率。\n"
                "7. 整理时间线、根因假设、证据截图和后续预防措施。"
            ),
            "rollback_plan": (
                "回滚触发条件：处置动作导致交易错误率上升、批处理状态异常，"
                "或锁等待没有按预期下降。\n\n"
                "- 立即停止进一步会话处置。\n"
                "- 恢复被暂停的批处理或限流配置，并通知应用负责人观察。\n"
                "- 保留处置前后 LOCKWAITS、应用状态和错误率证据。\n"
                "- 如已 force application，确认事务回滚完成且数据一致性检查通过。\n"
                "- 将处置动作纳入故障复盘，不再扩大影响面。"
            ),
            "precheck_sql": (
                "-- 锁等待明细\n"
                "SELECT * FROM SYSIBMADM.LOCKWAITS WHERE TABSCHEMA='ACCT' FETCH FIRST 50 ROWS ONLY;\n\n"
                "-- 当前应用和执行 SQL\n"
                "SELECT APPLICATION_HANDLE, APPLICATION_NAME, CLIENT_USERID, UOW_START_TIME\n"
                "FROM SYSIBMADM.APPLICATIONS\n"
                "ORDER BY UOW_START_TIME ASC FETCH FIRST 50 ROWS ONLY;\n\n"
                "-- 长事务观察\n"
                "SELECT * FROM SYSIBMADM.MON_CURRENT_UOW FETCH FIRST 50 ROWS ONLY;"
            ),
            "acceptance_checklist": (
                "- [ ] 锁持有者、等待者和等待链证据已保存。\n"
                "- [ ] 所有处置动作均有应急指挥批准。\n"
                "- [ ] 接口延迟和锁等待数量回落到约定阈值。\n"
                "- [ ] 未出现新的账户交易错误尖峰。\n"
                "- [ ] 故障时间线、根因假设和预防项已形成复盘材料。\n"
                "- [ ] 未经批准没有执行 kill session。"
            ),
        }
    if scenario == "add_column":
        return {
            "risk_assessment": (
                f"风险等级：{risk_level}\n\n"
                "- 兼容性：新增可空字段通常风险较低，但需确认应用 ORM、ETL 和审计查询兼容。\n"
                "- z/OS 影响：需要确认 package rebind、授权和变更窗口要求。\n"
                "- 写入压力：审计表写入量高，执行时需观察 DDL 锁和应用错误。\n"
                "- 下游影响：对账、复制和报表字段映射需确认不因新增列失败。\n"
                "- 回退限制：DDL 回退可能比执行更敏感，需要准备逻辑禁用方案。"
            ),
            "runbook": (
                "1. 确认新增字段为可空，应用版本已兼容未知列。\n"
                "2. 采集表结构、依赖对象、package 状态和写入基线。\n"
                "3. 在窗口内执行 ALTER TABLE ADD COLUMN。\n"
                "4. 如平台要求，执行或安排 package rebind。\n"
                "5. 验证新字段可查询、旧写入路径不受影响。\n"
                "6. 通知审计、对账和下游同步负责人验证字段映射。\n"
                "7. 归档 DDL、结构截图和业务验证结论。"
            ),
            "rollback_plan": (
                "回滚触发条件：新增字段导致写入失败、package 异常或下游同步中断。\n\n"
                "- 立即停止依赖新字段的应用发布或配置开关。\n"
                "- 如尚未被应用写入，评估 DROP COLUMN 或平台等效回退动作。\n"
                "- 如不允许物理回退，采用逻辑回退：应用忽略该字段并恢复旧映射。\n"
                "- 重新验证旧写入路径、对账任务和审计查询。\n"
                "- 记录字段状态、回退限制和后续清理计划。"
            ),
            "precheck_sql": (
                "-- 字段是否已存在\n"
                "SELECT NAME, COLTYPE, LENGTH, NULLS\n"
                "FROM SYSIBM.SYSCOLUMNS\n"
                "WHERE TBCREATOR='PAY' AND TBNAME='TXN_AUDIT' AND NAME='CHANNEL_CD';\n\n"
                "-- 表依赖对象\n"
                "SELECT * FROM SYSIBM.SYSRELS WHERE CREATOR='PAY' FETCH FIRST 20 ROWS ONLY;\n\n"
                "-- 高峰写入观察由平台监控补充，执行前记录 TPS 和错误率基线。"
            ),
            "acceptance_checklist": (
                "- [ ] CHANNEL_CD 字段存在且允许为空。\n"
                "- [ ] 旧版本写入路径无新增错误。\n"
                "- [ ] package/rebind 要求已确认并执行。\n"
                "- [ ] 审计查询和对账批处理验证通过。\n"
                "- [ ] 下游字段映射负责人已确认。\n"
                "- [ ] 逻辑回退方案已写入变更记录。"
            ),
        }
    return {}


def fixture_analysis(case: Case) -> dict:
    operation = case.change_type.lower()
    risk_level = "高" if case.priority == "P1" or "数据修复" in operation else "中"
    artifacts = {
        "risk_assessment": (
            f"风险等级：{risk_level}\n\n"
            "- 锁影响：确认执行路径不会产生长时间排他锁。\n"
            "- 性能影响：变更前收集访问计划、行数和表空间余量。\n"
            "- 同步/审计：确认下游作业、复制链路和审计触发器不会放大影响。\n"
            "- 业务影响：与应用负责人和批处理负责人确认维护窗口。\n"
            "- 回滚准备：提前准备精确回滚 SQL 和成功/失败判定点。"
        ),
        "runbook": (
            "1. 在运维沟通群宣布变更开始，并记录审批人。\n"
            "2. 采集基线：活动会话、锁等待、行数、访问计划和表空间使用率。\n"
            "3. 确认没有冲突批处理、长事务或未关闭的变更窗口。\n"
            "4. 在维护窗口内执行已评审 SQL 或操作命令。\n"
            "5. 每 5 分钟观察锁等待、日志使用量、CPU 和应用错误率。\n"
            "6. 执行验收 SQL，并与预期计数或性能指标比对。\n"
            "7. 将证据、时间点、执行人和最终状态写回变更记录。"
        ),
        "rollback_plan": (
            "回滚触发条件：验收计数不一致、锁等待持续超过 5 分钟，"
            "或应用错误率超过事先约定阈值。\n\n"
            "- 立即停止后续 SQL 执行。\n"
            "- 如果创建了索引，删除新增索引，并按需执行定向 RUNSTATS。\n"
            "- 如果修改了数据，从预先准备的备份表恢复受影响记录。\n"
            "- 重新执行变更前验证 SQL，并通知应用负责人。\n"
            "- 将回滚证据、时间点和影响范围追加到审计记录。"
        ),
        "precheck_sql": (
            "-- 活动会话和锁等待\n"
            "SELECT * FROM SYSIBMADM.LOCKWAITS FETCH FIRST 20 ROWS ONLY;\n\n"
            "-- 表行数和统计信息新鲜度\n"
            "SELECT TABSCHEMA, TABNAME, CARD, STATS_TIME\n"
            "FROM SYSCAT.TABLES\n"
            "WHERE TABSCHEMA NOT LIKE 'SYS%'\n"
            "ORDER BY STATS_TIME ASC\n"
            "FETCH FIRST 20 ROWS ONLY;\n\n"
            "-- 表空间余量\n"
            "SELECT TBSP_NAME, TBSP_USED_PAGES, TBSP_FREE_PAGES\n"
            "FROM SYSIBMADM.TBSP_UTILIZATION;"
        ),
        "acceptance_checklist": (
            "- [ ] 变更单已有明确业务审批。\n"
            "- [ ] 基线证据已采集并上传。\n"
            "- [ ] SQL 或命令与评审版本完全一致。\n"
            "- [ ] 验收计数或性能指标符合预期。\n"
            "- [ ] 未观察到新的锁等待或应用错误尖峰。\n"
            "- [ ] 未触发回滚；如触发，回滚证据完整。\n"
            "- [ ] 已向相关干系人发送最终沟通。"
        ),
        "communication_summary": (
            f"{case.target_system} 的变更「{case.title}」已具备受控执行条件。"
            "本方案包含前置检查证据、逐步执行 Runbook、回滚触发标准和变更后验收。"
            "如果锁等待、验收差异或应用错误率超过阈值，运维将立即暂停并启动回滚决策。"
        ),
    }
    artifacts.update(_scenario_artifacts(case, risk_level))
    return {
        "summary": (
            f"{case.target_system} 的 {case.db_type} 变更：{case.change_type}。"
            f"建议风险等级为{risk_level}；执行前需要准备检查证据、限时 Runbook、"
            "明确回滚负责人，并在变更后完成验收验证。"
        ),
        "artifacts": artifacts,
    }
