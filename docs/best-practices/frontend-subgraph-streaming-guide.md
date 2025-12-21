 SubGraph 渲染2主题前端如何支持 SubAgent 的中间执行步骤流渲染渲染生命周期](#渲染生命周期)
5. [中间步骤的处理](#中间步骤的处理)
6. [SubAgent 卡片的替换subagent-卡片的替换7当前实现的特性当前实现的特性8向向。当 treamSs=rue会自动解析格的事件，前端可以看到：

1.**中间步骤**：中的实时消息和状态更新2.**最终结果**：执行完成后卡片
关键特性：**在完成后被替换为最终的 SubAgent 卡片**。前端：SE事件流└─ └─   // 根图消息|subagent_name└─   // SubAgent 中间更新messg└─ [Mssg,MessageTlMeta]//SubAgent中间消息├upates│└─task: {messages: [...]}// 根图 tak 节点更新（包含 ubAgnt结果）│
└─:end └─ :{}解析与累积E事件流↓(SDKsSm解析├─[] 所有消息（包括SubAnt）├─
└─前端处理流程.[] +getMMeta() ↓(ChatIfacprocss)┌─────────────────────────────────────────┐│Mp:Mp<mId,            ││        ││        ││ }>                       │└─────────────────────────────────────────┘↓ (组件)
┌─────────────────────────────────────────┐
│1.消息内容          │
│ 2. 渲染 T（非 tak）│
│3.提取并渲染SbAg（task类型） │
────────────────────────────────────────┘MessgeMessge
type:"human"|"ai"|"tool";cotnt|ConentBloc[];tool_cll?TolCall[];
  adioal_ag{
ool_cll?ToCall[];
}###2. ToolCall来自消息元数据
interface ToolCall string; string;  //||"cde_execuor|
args:Record<string unknown>;?string;r" | "interupted;3从 ToolCall 完整参数4ProcessedMessg前端内部结构intfaceProcessedMssglCalllCallhwAvaa:boolea 是否显示头像（消息类型变化时）
}
```

---

##渲染生命周期
###阶段1：SubAgnt执行开始
**触发条件**：后端发送`eventupdates|ubagen_ame`

```
时间线：T0:后端开始执行SAgn  ↓
T1:前端收到vupdates|ubagen_ame↓
T2SDK累积消息到stream.messages
↓
T3:ChatInterface.processedMessages更新
↓
T4:ChatMessage组件重新渲染
├─显示SubAgent的中间消息（如果有）
└─显示SubAgent的中间状态更新**前端看到的**：
 SubAgent 的实时执行消息
 中间步骤的输出-执行状态的更新阶段2：执行完成

**触发条件**：后端发送 `event: upd` 包含 ak 节点的最终结果时间线：
T5:后端 ak节点执行完成
 ↓T6:前端收到ven: pdates（根图k 节点更新）├─ da{tsk:messages: [...]}}│└─ 包含 SbAget的最终结果↓
T7:SDK累积消息到sremssge├─新增AI消息（包含_c）│└─_c0].nmtask│└─_cs[0]"sbgen_nme"│└─_cs[0]ul=fialrul"↓T8htIterfc.prcessedMessgs 更新├─创建新的sMa 条目└─提取_c↓
T9htMg组件重新渲染├─过滤k├─转换为 └─显示SubAgen 卡片（最终结果）前端看到的中间步骤消息被替换为SubAgen卡片显示最终的 input/output-可查看详细信息

---

## 中间步骤的处
### 1. 中间步骤来源中间步骤来自 执行过程中的多个SS 事件：

```
v:msa|a_nm↓包含 内部的消息流
  ├─ 思考过程
 ├─工具调用 ├─工具结果  └─ 最终回复eve:updas|sa_ame
↓包含内部的状态更新├─节点执行状态├─中间结果└─错误信息

### 2. 中间步骤的累积SDK的`sSream`钩子自处理**：DK部逻辑（伪代码）f(v.srWth("messaes|"))//累积到 srm.messges
eam.messas.psh(...messgeDa)even.strsWith("us|)//累积到ream.values（通过upes事件）
 srem.vlue= mgeUpate(seam.valuespdateData)}```

###3.中间步骤的渲染

**ChatInterface中的处理**

```typ
cstcsedMessages = seMemo(()={smsageMaewMap();
//遍历所有消息（包括SbAget的中间消息）
  messg.frEach((message:Message)=>{messgea//提取该消息中的 ol_callsconsttoolCalls=extrcToolClls(msage);
   messgeMpe(mesae.id, messge,
        oolCll,
      })//.. 其他消息类型处理
}Arrayfrom(mesaeMp.vles());
}[messages]**ChatMessage中**：typescript// 渲染消息内容{hasCo && (<iv clssN=""><MarkdownConconnt={Conen} /></div>
)}

//2.渲染非task的ToolCall（中间步骤）{haToollls &&(<divclasNe="t-4 flx w-full flx-col">{oolCll.mp(:ToolCall)=>{
if(.name==="tak") rtrnull;//跳
    reurn <TBoxky={toolCall.id} toolCall={oolCall}/>;})}
</div>
)}
// 3SubAgent（task类型）
{!sUser && &&(  <div className="flex w-fit max-w-full flex-colgap-4">
{()subAgent={subAgent}))}
</dv>
)}
```

---

##卡片的替换机制

### 1替换的本质
**不是真正的"替换"，而是"覆盖"**：

```
时间T4：显示中间步骤
┌─────────────────────────────┐
│AIMessage(SubAgent中间││├─思考过程││├─工具调用结果     ││└─ 中输出  │
└─────────────────────────────┘

时间 T9：┌─────────────────────────────┐│AIMessage() │
│ ├─ SubAgenIndicor│
││└─sa_ye名称    ││└─展开面板 │
│    ├─ In │
│    └─ Oput             │└─────────────────────────────┘
2替换的原因

消息来源不同
```
中间步骤
 来even: messges|a_name
  └─这是生成  └─显示为普通的I 消息

最终结果
  来自 event: updates根图 task 节点  └─ 这是根图收到的SbAgnt 执行结果
  └─ 包含在 tool_clls
  └─ 显示为 卡片
```

### 3. 替换的时机

**当新的 AI消息到达时**ChaI中的rocMessaes更新
onsprossMessags=seMm(()= { //每次msaes数组变化时重新计算  //新的I 消息会创建新的 ssagMap条目 //旧的中间步骤消息仍然存在，但被新消息覆盖
},[mesaes])  // ←依赖mesas 数组
```

**具体流程**：

```
T4 时刻：saes=[urMg,santIermediaMsg ↓proessdMssas 生成 ├─rMsg →显示用户消息  └─antIerdatM → 显示中间步骤

9 时刻：ssag[rsantIerdatsg,kRsulMsg]↓pocsdMess 重新计算├─ eM→显示用户消息├─aInterdatMg→显示中间步骤（仍然存在）└─askRsuM→显示S 卡片（新增）```

**关键点**：中间步骤消息**不会被删除**，而是**新增了一个包含最终结果的消息**。

###4.为什么看起来"消失"了

**原因**：

1.**消息顺序**：新的skRlMg 在最后，会显示在下方
2. **视觉焦点**：S 卡片更显眼，吸引用户注意3.**用户预期**：用户期望看到最终结果，而不是中间步骤
4.**滚动位置**：新消息到达时，用户可能已经滚动，看不到中间步骤

**实际上**：中间步骤消息仍然在`procesdMesages`中，只是被新消息"压下去"了。
---

##当前实现的特性

###✅已支持

1.**SbAg的识别**-通过`toolCall.name==="task"`识别-通过`ooCallags["subag_ye"]`获取类型
2.**中间步骤的流式显示**
-通过`v: msge|a_ph`接收中间消息-通过`v: dae|a_ah` 接收中间更新-实时显示在聊天界面
3**最终结果的卡片展示**-SIndicor：显示名称和展开按钮-展开面板：显示 和o-可折叠/展开查看详情

4.**多层级S 支持**-通过`event|parent/child`格式支持嵌套 -前端可以区分不同层级的事件

5.**执行状态追踪**
-`oolCalstats`：pdng/copd/rror/rrutd
   实时更新执行状态

### ⚠️当前限制

. **中间步骤的可见性**  -中间步骤在最终卡片出现后不再显示
-用户需要向上滚动才能看到中间步骤2.**中间步骤的持久化**
-中间步骤消息不会被保存到S卡片中-无法在最终卡片中查看执行过程3.执行进度的显示    无法显示 SubAgent进度条   无法当前的
4.中间结果的聚合   无法将中间步骤结果聚合到最终卡片中   无法显示完整的执行轨迹

---方向

### 向1保留中间步骤的可见性**目标**：卡片中显示执行过程

**实现方案**intfacubAgntid: trin;
  namtrinubAgentNamesringnputunknown>;
  output?: Record<, unknownstatus: "pnding" | "ctve"|"completed"| "error"中间步骤iermedaeStepstitmpumber;type:"mes"| "updae"| "error";conntknown;
  }
//新增：执行进度
executoProgress?: {
    crrenSeptotalSteps:number percentage:number前**卡片中显示中间步骤
{iExpndd(s.id) &&   <div clasNam"..."
 {*Ip*/} <h4>Inp</4>
<MkownContnt co{...}/>{*新增：中间步骤*/} {.iemdiaeSteps&&       <h4>ExcuionSteps<h4>    .intermediateStep(tep,idx) (
          divxclasNam="...">
            <spa>{sep.type}</span>
            <MarkdownContent contenttep.content
          </div>
        )      </>)}

    新增：执行进度*/}
    {s.executionProgress&& (
      <div className="...">    <ProgressB alu={st.execuionProgresercentge}/
 span>{st.execuionrogrscrrtSep}</pn>
     </d>
    )}

    {/* Output */}
   <h4>Output<h4 <MarkdownContentcontent={... />div}### 方向 2实时更新SubAgent卡片目标卡片在执行过程中实更新**方案**：1.后端SSE事件包含 ID      eve:pdae|a_nm da:{
     sa_id:"tsk-xxx",   inemdit_sep:...}}
   ```

2. **前端**：根据 ID实时更新卡片
   ```ypcip // 订阅 ve: pdae|a_pathcont handleSUpde(aId, upd=>  mapa =>
         sa=== aId ?{...a, inemditStep: [...(.intrmediateStep || [, update] }
           : sa
       )
     )   };
   向 3：分离中间步骤和最终结果目标在不同的UI 区域和最终结果**实现方案**：
```
┌─────────────────────────────────┐
│执行过程实时更新             │├─────────────────────────────────┤│Step 1: 初始化                  │
│ep 2: 执行工具 A              │
│ S 3: 处理结果                │
│ Stp 4: 执行工具 B             │
├─────────────────────────────────┤
│最终结果（ 卡片）       │
├─────────────────────────────────┤│ Input: ...                     ││ Output: ...                    │
└─────────────────────────────────┘```

### 当前状态**确实可以看到 SubAgent 的中间执行步骤**，这些步骤 `event:messages|subagent_path`和event: pdates|ubagn_pth流式传输。但在完成后，最终的 SubAgent 卡片会出现在聊天界面的下方，使得中间步骤看起来"消失"了

### 核心机制

1. ****：来自 SubAgent 内部的消息和更新，为普通的 AI消息
2.**最终结果**：来自根图k 节点的执行结果显示为 SubAgent
3. **替换**：不是真正的替换，而是新增消息，中间步骤仍然存在但被新息压下去

### 改进方向为了让用户更好地理解 SubAgent 的过程可以：
1.  卡片中保留中间步骤的记录
2.实更新ubAgen 卡片的执行进度
3.分离骤和最终结果显示区域
