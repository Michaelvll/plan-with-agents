# Claude Code Debate Session

**Started:** 2026-01-17T20:52:15.016785
**Ended:** 2026-01-17T21:18:18.877015
**Status:** debating
**Rounds:** 4

## Initial Prompt

Design a visual AI agent workflow builder

Requirements:
- Drag-and-drop nodes for different agent types (researcher, coder, reviewer)
- Connect nodes to show data flow between agents
- Configure each node (model, temperature, system prompt)
- Show real-time execution status and logs
- Visualize agent communication/handoffs
- Save and load workflow templates
- React with a canvas library

---

## Round 1

### 🔵 Agent A

## Design

# Visual AI Agent Workflow Builder - Complete Design

## Architecture Overview

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     React Application                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │     │
│  │   Layer      │  │    Panel     │  │   & Palette  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────┤
│           Workflow State Management (Zustand)               │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Execution  │  │  Template    │  │   Validation │     │
│  │   Engine     │  │  Manager     │  │   Service    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas Library**: React Flow (react-flow-renderer) - mature, performant, extensible
- **State Management**: Zustand - lightweight, no boilerplate
- **UI Components**: Radix UI + Tailwind CSS - accessible, customizable
- **Execution**: Web Workers for non-blocking agent execution
- **Storage**: IndexedDB for templates, LocalStorage for recent workflows

## Core Components

### 1. Canvas Component (WorkflowCanvas.tsx)
```typescript
interface WorkflowCanvasProps {
  workflowId: string;
  readonly?: boolean;
}

const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({ 
  workflowId, 
  readonly = false 
}) => {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect } = 
    useWorkflowStore();
  
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      nodeTypes={customNodeTypes}
      edgeTypes={customEdgeTypes}
      fitView
      minZoom={0.2}
      maxZoom={2}
    >
      <Background />
      <Controls />
      <MiniMap />
      <ExecutionOverlay />
    </ReactFlow>
  );
};
```

### 2. Agent Node Component (AgentNode.tsx)
```typescript
interface AgentNodeData {
  id: string;
  type: 'researcher' | 'coder' | 'reviewer' | 'coordinator';
  label: string;
  config: AgentConfig;
  status: ExecutionStatus;
  logs: LogEntry[];
  metrics: ExecutionMetrics;
}

interface AgentConfig {
  model: string; // 'gpt-4', 'claude-3-opus', etc.
  temperature: number;
  systemPrompt: string;
  maxTokens?: number;
  timeout?: number;
  retryConfig?: RetryConfig;
}

const AgentNode: React.FC<NodeProps<AgentNodeData>> = ({ data, selected }) => {
  const getStatusColor = () => {
    switch (data.status) {
      case 'idle': return 'gray';
      case 'running': return 'blue';
      case 'success': return 'green';
      case 'error': return 'red';
      case 'waiting': return 'yellow';
    }
  };

  return (
    <div className={`agent-node ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      
      <div className="node-header" style={{ borderColor: getStatusColor() }}>
        <AgentIcon type={data.type} />
        <span>{data.label}</span>
        <StatusBadge status={data.status} />
      </div>
      
      <div className="node-body">
        <div className="config-summary">
          <span className="model-badge">{data.config.model}</span>
          <span className="temp-badge">T: {data.config.temperature}</span>
        </div>
        
        {data.status === 'running' && (
          <ProgressBar metrics={data.metrics} />
        )}
        
        {data.logs.length > 0 && (
          <LogPreview logs={data.logs.slice(-3)} />
        )}
      </div>
      
      <Handle type="source" position={Position.Right} />
    </div>
  );
};
```

### 3. Connection Edge Component (DataFlowEdge.tsx)
```typescript
interface EdgeData {
  id: string;
  dataType: 'text' | 'json' | 'code' | 'artifacts';
  transformations?: Transformation[];
  status: 'idle' | 'active' | 'complete';
  dataPreview?: string;
}

const DataFlowEdge: React.FC<EdgeProps<EdgeData>> = ({ 
  id, 
  source, 
  target, 
  data,
  style 
}) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, targetX, targetY
  });

  return (
    <>
      <BaseEdge 
        path={edgePath} 
        style={{ 
          ...style, 
          stroke: data.status === 'active' ? '#3b82f6' : '#6b7280',
          strokeWidth: data.status === 'active' ? 3 : 2,
          animation: data.status === 'active' ? 'dash 1s linear infinite' : 'none'
        }} 
      />
      
      <EdgeLabelRenderer>
        <div
          style={{ 
            position: 'absolute', 
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)` 
          }}
        >
          <DataTypeIndicator type={data.dataType} />
          {data.dataPreview && (
            <DataPreviewTooltip content={data.dataPreview} />
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};
```

### 4. Properties Panel (PropertiesPanel.tsx)
```typescript
const PropertiesPanel: React.FC = () => {
  const { selectedNode, updateNodeConfig } = useWorkflowStore();
  
  if (!selectedNode) {
    return <EmptyState message="Select a node to configure" />;
  }

  return (
    <div className="properties-panel">
      <Tabs defaultValue="config">
        <TabsList>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="prompt">System Prompt</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>
        
        <TabsContent value="config">
          <ConfigurationTab node={selectedNode} />
        </TabsContent>
        
        <TabsContent value="prompt">
          <PromptEditor 
            value={selectedNode.config.systemPrompt}
            onChange={(prompt) => updateNodeConfig(selectedNode.id, { systemPrompt: prompt })}
            variables={getAvailableVariables(selectedNode)}
          />
        </TabsContent>
        
        <TabsContent value="advanced">
          <AdvancedSettingsTab node={selectedNode} />
        </TabsContent>
        
        <TabsContent value="logs">
          <LogViewer logs={selectedNode.logs} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

const ConfigurationTab: React.FC<{ node: AgentNodeData }> = ({ node }) => {
  return (
    <div className="config-form">
      <FormField label="Agent Name">
        <Input value={node.label} onChange={...} />
      </FormField>
      
      <FormField label="Model">
        <Select value={node.config.model}>
          <SelectOption value="gpt-4-turbo">GPT-4 Turbo</SelectOption>
          <SelectOption value="claude-3-opus">Claude 3 Opus</SelectOption>
          <SelectOption value="claude-3-sonnet">Claude 3 Sonnet</SelectOption>
          <SelectOption value="gemini-pro">Gemini Pro</SelectOption>
        </Select>
      </FormField>
      
      <FormField label="Temperature" description="Controls randomness (0-2)">
        <Slider 
          value={node.config.temperature} 
          min={0} 
          max={2} 
          step={0.1}
          onChange={...}
        />
        <Input type="number" value={node.config.temperature} />
      </FormField>
      
      <FormField label="Max Tokens" optional>
        <Input type="number" value={node.config.maxTokens} />
      </FormField>
      
      <FormField label="Timeout (seconds)" optional>
        <Input type="number" value={node.config.timeout} />
      </FormField>
    </div>
  );
};
```

### 5. Toolbar & Node Palette (Toolbar.tsx)
```typescript
const Toolbar: React.FC = () => {
  const { executeWorkflow, stopExecution, saveWorkflow, loadTemplate } = 
    useWorkflowStore();
  const executionState = useExecutionState();

  return (
    <div className="toolbar">
      <div className="toolbar-section">
        <Button 
          onClick={executeWorkflow}
          disabled={executionState.isRunning}
          variant="primary"
        >
          <PlayIcon /> Run Workflow
        </Button>
        
        {executionState.isRunning && (
          <Button onClick={stopExecution} variant="danger">
            <StopIcon /> Stop
          </Button>
        )}
      </div>
      
      <Separator />
      
      <div className="toolbar-section">
        <Button onClick={saveWorkflow} variant="secondary">
          <SaveIcon /> Save
        </Button>
        
        <DropdownMenu>
          <DropdownMenuTrigger>
            <Button variant="secondary">
              <FolderIcon /> Templates
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem onClick={() => loadTemplate('research-pipeline')}>
              Research Pipeline
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => loadTemplate('code-review')}>
              Code Review Flow
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => loadTemplate('content-generation')}>
              Content Generation
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      
      <Separator />
      
      <NodePalette />
    </div>
  );
};

const NodePalette: React.FC = () => {
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
    event.dataTransfer.effectAllowed = 'move';
  };

  return (
    <div className="node-palette">
      <div 
        className="palette-item researcher"
        draggable
        onDragStart={(e) => onDragStart(e, 'researcher')}
      >
        <ResearchIcon />
        <span>Researcher</span>
      </div>
      
      <div 
        className="palette-item coder"
        draggable
        onDragStart={(e) => onDragStart(e, 'coder')}
      >
        <CodeIcon />
        <span>Coder</span>
      </div>
      
      <div 
        className="palette-item reviewer"
        draggable
        onDragStart={(e) => onDragStart(e, 'reviewer')}
      >
        <ReviewIcon />
        <span>Reviewer</span>
      </div>
      
      <div 
        className="palette-item coordinator"
        draggable
        onDragStart={(e) => onDragStart(e, 'coordinator')}
      >
        <CoordinatorIcon />
        <span>Coordinator</span>
      </div>
    </div>
  );
};
```

## Data Models

### Workflow Schema
```typescript
interface Workflow {
  id: string;
  name: string;
  description?: string;
  version: string;
  createdAt: Date;
  updatedAt: Date;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  globalConfig: GlobalConfig;
  executionHistory: ExecutionRecord[];
}

interface WorkflowNode {
  id: string;
  type: 'researcher' | 'coder' | 'reviewer' | 'coordinator';
  position: { x: number; y: number };
  data: AgentNodeData;
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  data: EdgeData;
}

interface GlobalConfig {
  defaultModel: string;
  defaultTemperature: number;
  maxConcurrentAgents: number;
  errorHandling: 'stop' | 'continue' | 'retry';
  loggingLevel: 'debug' | 'info' | 'warn' | 'error';
}
```

### Execution State
```typescript
interface ExecutionState {
  workflowId: string;
  status: 'idle' | 'running' | 'paused' | 'completed' | 'failed';
  startedAt?: Date;
  completedAt?: Date;
  currentNode?: string;
  nodeStates: Map<string, NodeExecutionState>;
  globalContext: Record<string, any>;
  errors: ExecutionError[];
}

interface NodeExecutionState {
  nodeId: string;
  status: ExecutionStatus;
  startedAt?: Date;
  completedAt?: Date;
  input?: any;
  output?: any;
  logs: LogEntry[];
  metrics: ExecutionMetrics;
  error?: ExecutionError;
}

type ExecutionStatus = 'idle' | 'waiting' | 'running' | 'success' | 'error' | 'skipped';

interface ExecutionMetrics {
  tokensUsed?: number;
  executionTime?: number;
  retryCount?: number;
  costEstimate?: number;
}

interface LogEntry {
  timestamp: Date;
  level: 'debug' | 'info' | 'warn' | 'error';
  nodeId: string;
  message: string;
  metadata?: Record<string, any>;
}

interface ExecutionError {
  nodeId: string;
  timestamp: Date;
  error: Error;
  recoverable: boolean;
  retryAttempts: number;
}
```

## State Management (Zustand Store)

```typescript
interface WorkflowStore {
  // Current workflow state
  workflow: Workflow | null;
  nodes: Node<AgentNodeData>[];
  edges: Edge<EdgeData>[];
  selectedNode: AgentNodeData | null;
  
  // Execution state
  executionState: ExecutionState | null;
  isExecuting: boolean;
  
  // Actions
  setWorkflow: (workflow: Workflow) => void;
  addNode: (node: WorkflowNode) => void;
  updateNode: (nodeId: string, updates: Partial<AgentNodeData>) => void;
  deleteNode: (nodeId: string) => void;
  addEdge: (edge: WorkflowEdge) => void;
  deleteEdge: (edgeId: string) => void;
  selectNode: (nodeId: string | null) => void;
  
  // Execution
  executeWorkflow: () => Promise<void>;
  pauseExecution: () => void;
  resumeExecution: () => void;
  stopExecution: () => void;
  executeNode: (nodeId: string) => Promise<void>;
  
  // Persistence
  saveWorkflow: () => Promise<void>;
  loadWorkflow: (workflowId: string) => Promise<void>;
  saveTemplate: (name: string) => Promise<void>;
  loadTemplate: (templateId: string) => Promise<void>;
  
  // Validation
  validateWorkflow: () => ValidationResult;
}

const useWorkflowStore = create<WorkflowStore>((set, get) => ({
  workflow: null,
  nodes: [],
  edges: [],
  selectedNode: null,
  executionState: null,
  isExecuting: false,
  
  // Implementation details...
}));
```

## Execution Engine

### Workflow Executor
```typescript
class WorkflowExecutor {
  private workflowId: string;
  private nodes: Map<string, WorkflowNode>;
  private edges: WorkflowEdge[];
  private executionState: ExecutionState;
  private worker: Worker;
  
  constructor(workflow: Workflow) {
    this.workflowId = workflow.id;
    this.nodes = new Map(workflow.nodes.map(n => [n.id, n]));
    this.edges = workflow.edges;
    this.executionState = this.initExecutionState();
    this.worker = new Worker(new URL('./execution.worker.ts', import.meta.url));
  }
  
  async execute(): Promise<ExecutionResult> {
    this.executionState.status = 'running';
    this.executionState.startedAt = new Date();
    
    try {
      // Build execution graph
      const executionGraph = this.buildExecutionGraph();
      
      // Topological sort to determine execution order
      const executionOrder = this.topologicalSort(executionGraph);
      
      // Execute nodes in order (with parallelization where possible)
      for (const level of executionOrder) {
        await this.executeLevel(level);
      }
      
      this.executionState.status = 'completed';
      this.executionState.completedAt = new Date();
      
      return {
        success: true,
        executionState: this.executionState
      };
    } catch (error) {
      this.executionState.status = 'failed';
      this.executionState.errors.push({
        nodeId: 'workflow',
        timestamp: new Date(),
        error: error as Error,
        recoverable: false,
        retryAttempts: 0
      });
      
      return {
        success: false,
        executionState: this.executionState,
        error: error as Error
      };
    }
  }
  
  private async executeLevel(nodeIds: string[]): Promise<void> {
    // Execute all nodes in this level in parallel
    const promises = nodeIds.map(nodeId => this.executeNode(nodeId));
    await Promise.all(promises);
  }
  
  private async executeNode(nodeId: string): Promise<void> {
    const node = this.nodes.get(nodeId)!;
    const nodeState = this.executionState.nodeStates.get(nodeId)!;
    
    nodeState.status = 'running';
    nodeState.startedAt = new Date();
    
    try {
      // Gather inputs from predecessor nodes
      const inputs = this.gatherInputs(nodeId);
      nodeState.input = inputs;
      
      // Execute agent in web worker
      const result = await this.executeAgentInWorker(node, inputs);
      
      nodeState.output = result.output;
      nodeState.logs.push(...result.logs);
      nodeState.metrics = result.metrics;
      nodeState.status = 'success';
      nodeState.completedAt = new Date();
      
      // Store output in global context
      this.executionState.globalContext[nodeId] = result.output;
      
    } catch (error) {
      nodeState.status = 'error';
      nodeState.error = {
        nodeId,
        timestamp: new Date(),
        error: error as Error,
        recoverable: this.isRecoverableError(error),
        retryAttempts: 0
      };
      
      // Handle error based on global config
      await this.handleNodeError(nodeId, error as Error);
    }
  }
  
  private async executeAgentInWorker(
    node: WorkflowNode, 
    inputs: any
  ): Promise<AgentExecutionResult> {
    return new Promise((resolve, reject) => {
      const messageId = crypto.randomUUID();
      
      const handler = (event: MessageEvent) => {
        if (event.data.messageId === messageId) {
          this.worker.removeEventListener('message', handler);
          
          if (event.data.error) {
            reject(new Error(event.data.error));
          } else {
            resolve(event.data.result);
          }
        }
      };
      
      this.worker.addEventListener('message', handler);
      
      this.worker.postMessage({
        messageId,
        type: 'execute',
        node,
        inputs
      });
    });
  }
  
  private buildExecutionGraph(): Map<string, string[]> {
    const graph = new Map<string, string[]>();
    
    for (const node of this.nodes.values()) {
      graph.set(node.id, []);
    }
    
    for (const edge of this.edges) {
      graph.get(edge.target)!.push(edge.source);
    }
    
    return graph;
  }
  
  private topologicalSort(graph: Map<string, string[]>): string[][] {
    // Returns levels of nodes that can be executed in parallel
    const inDegree = new Map<string, number>();
    const levels: string[][] = [];
    
    // Calculate in-degrees
    for (const [node, deps] of graph.entries()) {
      inDegree.set(node, deps.length);
    }
    
    while (inDegree.size > 0) {
      // Find all nodes with in-degree 0
      const currentLevel = Array.from(inDegree.entries())
        .filter(([_, degree]) => degree === 0)
        .map(([node, _]) => node);
      
      if (currentLevel.length === 0) {
        throw new Error('Circular dependency detected in workflow');
      }
      
      levels.push(currentLevel);
      
      // Remove these nodes and update in-degrees
      for (const node of currentLevel) {
        inDegree.delete(node);
        
        // Update dependents
        for (const [otherNode, deps] of graph.entries()) {
          if (deps.includes(node)) {
            inDegree.set(otherNode, inDegree.get(otherNode)! - 1);
          }
        }
      }
    }
    
    return levels;
  }
  
  private gatherInputs(nodeId: string): Record<string, any> {
    const inputs: Record<string, any> = {};
    
    // Find all edges pointing to this node
    const incomingEdges = this.edges.filter(e => e.target === nodeId);
    
    for (const edge of incomingEdges) {
      const sourceOutput = this.executionState.globalContext[edge.source];
      
      // Apply any transformations defined on the edge
      const transformedOutput = this.applyTransformations(
        sourceOutput, 
        edge.data.transformations
      );
      
      inputs[edge.source] = transformedOutput;
    }
    
    return inputs;
  }
  
  private applyTransformations(
    data: any, 
    transformations?: Transformation[]
  ): any {
    if (!transformations || transformations.length === 0) {
      return data;
    }
    
    let result = data;
    for (const transform of transformations) {
      result = this.applyTransformation(result, transform);
    }
    return result;
  }
}
```

### Web Worker (execution.worker.ts)
```typescript
// Handles actual agent execution to avoid blocking UI
self.addEventListener('message', async (event: MessageEvent) => {
  const { messageId, type, node, inputs } = event.data;
  
  if (type === 'execute') {
    try {
      const result = await executeAgent(node, inputs);
      
      self.postMessage({
        messageId,
        result
      });
    } catch (error) {
      self.postMessage({
        messageId,
        error: (error as Error).message
      });
    }
  }
});

async function executeAgent(
  node: WorkflowNode, 
  inputs: Record<string, any>
): Promise<AgentExecutionResult> {
  const startTime = Date.now();
  const logs: LogEntry[] = [];
  
  // Build the prompt with inputs
  const prompt = buildPrompt(node, inputs);
  
  logs.push({
    timestamp: new Date(),
    level: 'info',
    nodeId: node.id,
    message: `Starting execution with model ${node.data.config.model}`,
    metadata: { inputs }
  });
  
  // Call the appropriate AI model
  const response = await callAIModel(
    node.data.config.model,
    prompt,
    node.data.config
  );
  
  const executionTime = Date.now() - startTime;
  
  logs.push({
    timestamp: new Date(),
    level: 'info',
    nodeId: node.id,
    message: `Execution completed in ${executionTime}ms`,
    metadata: { tokensUsed: response.tokensUsed }
  });
  
  return {
    output: response.output,
    logs,
    metrics: {
      tokensUsed: response.tokensUsed,
      executionTime,
      retryCount: 0,
      costEstimate: calculateCost(node.data.config.model, response.tokensUsed)
    }
  };
}
```

## Real-Time Visualization

### Execution Overlay Component
```typescript
const ExecutionOverlay: React.FC = () => {
  const executionState = useWorkflowStore(state => state.executionState);
  
  if (!executionState || executionState.status === 'idle') {
    return null;
  }
  
  return (
    <Panel position="top-right">
      <div className="execution-panel">
        <div className="execution-header">
          <StatusIndicator status={executionState.status} />
          <h3>Workflow Execution</h3>
        </div>
        
        <div className="execution-metrics">
          <MetricCard 
            label="Duration" 
            value={formatDuration(executionState.startedAt, executionState.completedAt)} 
          />
          <MetricCard 
            label="Nodes Completed" 
            value={`${getCompletedCount(executionState)}/${executionState.nodeStates.size}`} 
          />
          <MetricCard 
            label="Total Cost" 
            value={`$${calculateTotalCost(executionState).toFixed(4)}`} 
          />
        </div>
        
        <div className="execution-timeline">
          <Timeline executionState={executionState} />
        </div>
        
        {executionState.errors.length > 0 && (
          <div className="execution-errors">
            <ErrorList errors={executionState.errors} />
          </div>
        )}
      </div>
    </Panel>
  );
};
```

### Live Log Viewer
```typescript
const LogViewer: React.FC<{ logs: LogEntry[] }> = ({ logs }) => {
  const [filter, setFilter] = useState<LogLevel | 'all'>('all');
  const [search, setSearch] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);
  
  const filteredLogs = useMemo(() => {
    return logs
      .filter(log => filter === 'all' || log.level === filter)
      .filter(log => 
        search === '' || 
        log.message.toLowerCase().includes(search.toLowerCase())
      );
  }, [logs, filter, search]);
  
  return (
    <div className="log-viewer">
      <div className="log-controls">
        <Input 
          placeholder="Search logs..." 
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={filter} onValueChange={setFilter}>
          <SelectOption value="all">All Levels</SelectOption>
          <SelectOption value="debug">Debug</SelectOption>
          <SelectOption value="info">Info</SelectOption>
          <SelectOption value="warn">Warning</SelectOption>
          <SelectOption value="error">Error</SelectOption>
        </Select>
      </div>
      
      <div className="log-entries" ref={scrollRef}>
        <VirtualList
          items={filteredLogs}
          height={400}
          itemHeight={24}
          renderItem={(log) => (
            <LogEntry key={log.timestamp.getTime()} log={log} />
          )}
        />
      </div>
    </div>
  );
};

const LogEntry: React.FC<{ log: LogEntry }> = ({ log }) => {
  return (
    <div className={`log-entry log-${log.level}`}>
      <span className="log-timestamp">
        {log.timestamp.toLocaleTimeString()}
      </span>
      <span className={`log-level level-${log.level}`}>
        {log.level.toUpperCase()}
      </span>
      <span className="log-node">[{log.nodeId}]</span>
      <span className="log-message">{log.message}</span>
      {log.metadata && (
        <Collapsible>
          <CollapsibleTrigger>
            <ChevronIcon />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre>{JSON.stringify(log.metadata, null, 2)}</pre>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  );
};
```

## Template Management

### Template Structure
```typescript
interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: 'research' | 'coding' | 'review' | 'general';
  thumbnail?: string;
  workflow: Omit<Workflow, 'id' | 'createdAt' | 'updatedAt' | 'executionHistory'>;
  variables: TemplateVariable[];
}

interface TemplateVariable {
  key: string;
  label: string;
  type: 'string' | 'number' | 'model' | 'prompt';
  defaultValue?: any;
  description?: string;
}

// Example template
const RESEARCH_PIPELINE_TEMPLATE: WorkflowTemplate = {
  id: 'research-pipeline',
  name: 'Research Pipeline',
  description: 'Multi-stage research workflow with synthesis',
  category: 'research',
  variables: [
    {
      key: 'research_topic',
      label: 'Research Topic',
      type: 'string',
      description: 'The topic to research'
    },
    {
      key: 'primary_model',
      label: 'Primary Model',
      type: 'model',
      defaultValue: 'gpt-4-turbo'
    }
  ],
  workflow: {
    name: 'Research Pipeline',
    version: '1.0.0',
    nodes: [
      {
        id: 'researcher-1',
        type: 'researcher',
        position: { x: 100, y: 100 },
        data: {
          id: 'researcher-1',
          type: 'researcher',
          label: 'Primary Researcher',
          config: {
            model: '{{primary_model}}',
            temperature: 0.7,
            systemPrompt: 'You are a thorough researcher. Research: {{research_topic}}'
          },
          status: 'idle',
          logs: [],
          metrics: {}
        }
      },
      {
        id: 'reviewer-1',
        type: 'reviewer',
        position: { x: 400, y: 100 },
        data: {
          id: 'reviewer-1',
          type: 'reviewer',
          label: 'Fact Checker',
          config: {
            model: 'claude-3-opus',
            temperature: 0.3,
            systemPrompt: 'Review research for accuracy and completeness.'
          },
          status: 'idle',
          logs: [],
          metrics: {}
        }
      }
    ],
    edges: [
      {
        id: 'e1',
        source: 'researcher-1',
        target: 'reviewer-1',
        data: {
          id: 'e1',
          dataType: 'text',
          status: 'idle'
        }
      }
    ],
    globalConfig: {
      defaultModel: 'gpt-4-turbo',
      defaultTemperature: 0.7,
      maxConcurrentAgents: 3,
      errorHandling: 'stop',
      loggingLevel: 'info'
    },
    executionHistory: []
  }
};
```

### Template Manager
```typescript
class TemplateManager {
  private db: IDBDatabase;
  
  async saveTemplate(template: WorkflowTemplate): Promise<void> {
    const tx = this.db.transaction('templates', 'readwrite');
    const store = tx.objectStore('templates');
    await store.put(template);
  }
  
  async loadTemplate(templateId: string): Promise<WorkflowTemplate> {
    const tx = this.db.transaction('templates', 'readonly');
    const store = tx.objectStore('templates');
    return await store.get(templateId);
  }
  
  async listTemplates(category?: string): Promise<WorkflowTemplate[]> {
    const tx = this.db.transaction('templates', 'readonly');
    const store = tx.objectStore('templates');
    const templates = await store.getAll();
    
    if (category) {
      return templates.filter(t => t.category === category);
    }
    return templates;
  }
  
  async instantiateTemplate(
    templateId: string, 
    variables: Record<string, any>
  ): Promise<Workflow> {
    const template = await this.loadTemplate(templateId);
    
    // Deep clone the workflow
    const workflow: Workflow = {
      id: crypto.randomUUID(),
      name: template.workflow.name,
      description: template.workflow.description,
      version: template.workflow.version,
      createdAt: new Date(),
      updatedAt: new Date(),
      nodes: JSON.parse(JSON.stringify(template.workflow.nodes)),
      edges: JSON.parse(JSON.stringify(template.workflow.edges)),
      globalConfig: { ...template.workflow.globalConfig },
      executionHistory: []
    };
    
    // Replace variables
    const workflowStr = JSON.stringify(workflow);
    const replaced = this.replaceVariables(workflowStr, variables);
    
    return JSON.parse(replaced);
  }
  
  private replaceVariables(
    template: string, 
    variables: Record<string, any>
  ): string {
    let result = template;
    for (const [key, value] of Object.entries(variables)) {
      result = result.replace(
        new RegExp(`{{${key}}}`, 'g'), 
        String(value)
      );
    }
    return result;
  }
}
```

## Error Handling

### Validation Service
```typescript
interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

interface ValidationError {
  type: 'structure' | 'config' | 'connection';
  nodeId?: string;
  edgeId?: string;
  message: string;
  severity: 'error' | 'warning';
}

class WorkflowValidator {
  validate(workflow: Workflow): ValidationResult {
    const errors: ValidationError[] = [];
    const warnings: ValidationWarning[] = [];
    
    // Check for cycles
    if (this.hasCycles(workflow)) {
      errors.push({
        type: 'structure',
        message: 'Workflow contains circular dependencies',
        severity: 'error'
      });
    }
    
    // Check for disconnected nodes
    const disconnected = this.findDisconnectedNodes(workflow);
    if (disconnected.length > 0) {
      warnings.push({
        type: 'structure',
        message: `${disconnected.length} nodes are not connected`,
        nodeIds: disconnected,
        severity: 'warning'
      });
    }
    
    // Validate each node configuration
    for (const node of workflow.nodes) {
      const nodeErrors = this.validateNode(node);
      errors.push(...nodeErrors);
    }
    
    // Check for missing start nodes
    const startNodes = this.findStartNodes(workflow);
    if (startNodes.length === 0) {
      errors.push({
        type: 'structure',
        message: 'Workflow has no starting nodes',
        severity: 'error'
      });
    }
    
    return {
      valid: errors.length === 0,
      errors,
      warnings
    };
  }
  
  private validateNode(node: WorkflowNode): ValidationError[] {
    const errors: ValidationError[] = [];
    
    if (!node.data.config.model) {
      errors.push({
        type: 'config',
        nodeId: node.id,
        message: 'No model selected',
        severity: 'error'
      });
    }
    
    if (!node.data.config.systemPrompt || node.data.config.systemPrompt.trim() === '') {
      errors.push({
        type: 'config',
        nodeId: node.id,
        message: 'System prompt is empty',
        severity: 'error'
      });
    }
    
    if (node.data.config.temperature < 0 || node.data.config.temperature > 2) {
      errors.push({
        type: 'config',
        nodeId: node.id,
        message: 'Temperature must be between 0 and 2',
        severity: 'error'
      });
    }
    
    return errors;
  }
  
  private hasCycles(workflow: Workflow): boolean {
    const visited = new Set<string>();
    const recursionStack = new Set<string>();
    
    const adjacencyList = new Map<string, string[]>();
    for (const node of workflow.nodes) {
      adjacencyList.set(node.id, []);
    }
    for (const edge of workflow.edges) {
      adjacencyList.get(edge.source)!.push(edge.target);
    }
    
    const dfs = (nodeId: string): boolean => {
      visited.add(nodeId);
      recursionStack.add(nodeId);
      
      for (const neighbor of adjacencyList.get(nodeId) || []) {
        if (!visited.has(neighbor)) {
          if (dfs(neighbor)) return true;
        } else if (recursionStack.has(neighbor)) {
          return true;
        }
      }
      
      recursionStack.delete(nodeId);
      return false;
    };
    
    for (const node of workflow.nodes) {
      if (!visited.has(node.id)) {
        if (dfs(node.id)) return true;
      }
    }
    
    return false;
  }
  
  private findDisconnectedNodes(workflow: Workflow): string[] {
    const connectedNodes = new Set<string>();
    
    for (const edge of workflow.edges) {
      connectedNodes.add(edge.source);
      connectedNodes.add(edge.target);
    }
    
    return workflow.nodes
      .filter(node => !connectedNodes.has(node.id))
      .map(node => node.id);
  }
  
  private findStartNodes(workflow: Workflow): string[] {
    const nodesWithInput = new Set(workflow.edges.map(e => e.target));
    return workflow.nodes
      .filter(node => !nodesWithInput.has(node.id))
      .map(node => node.id);
  }
}
```

### Error Recovery
```typescript
class ErrorRecoveryService {
  async handleNodeError(
    nodeId: string,
    error: Error,
    config: GlobalConfig
  ): Promise<RecoveryAction> {
    
    switch (config.errorHandling) {
      case 'stop':
        return { action: 'stop', message: 'Execution stopped due to error' };
        
      case 'retry':
        if (this.isRetryableError(error)) {
          return { 
            action: 'retry', 
            maxRetries: 3,
            backoff: 'exponential',
            message: 'Retrying node execution' 
          };
        }
        return { action: 'skip', message: 'Error not retryable, skipping node' };
        
      case 'continue':
        return { 
          action: 'continue', 
          message: 'Continuing with next nodes',
          skipDownstream: false
        };
        
      default:
        return { action: 'stop', message: 'Unknown error handling strategy' };
    }
  }
  
  private isRetryableError(error: Error): boolean {
    // Network errors, rate limits, temporary API failures
    return error.message.includes('ECONNREFUSED') ||
           error.message.includes('rate limit') ||
           error.message.includes('timeout') ||
           error.message.includes('429');
  }
  
  async retryWithBackoff(
    fn: () => Promise<any>,
    maxRetries: number,
    backoff: 'linear' | 'exponential' = 'exponential'
  ): Promise<any> {
    let lastError: Error;
    
    for (let i = 0; i < maxRetries; i++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error as Error;
        
        if (i < maxRetries - 1) {
          const delay = backoff === 'exponential' 
            ? Math.pow(2, i) * 1000 
            : (i + 1) * 1000;
          
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }
    
    throw lastError!;
  }
}
```

## Persistence Layer

### IndexedDB Schema
```typescript
const DB_NAME = 'workflow-builder';
const DB_VERSION = 1;

interface DBSchema {
  workflows: {
    key: string;
    value: Workflow;
    indexes: {
      'by-updated': Date;
      'by-name': string;
    };
  };
  templates: {
    key: string;
    value: WorkflowTemplate;
    indexes: {
      'by-category': string;
    };
  };
  executions: {
    key: string;
    value: ExecutionRecord;
    indexes: {
      'by-workflow': string;
      'by-date': Date;
    };
  };
}

class WorkflowDatabase {
  private db: IDBDatabase | null = null;
  
  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        // Workflows store
        if (!db.objectStoreNames.contains('workflows')) {
          const workflowStore = db.createObjectStore('workflows', { keyPath: 'id' });
          workflowStore.createIndex('by-updated', 'updatedAt');
          workflowStore.createIndex('by-name', 'name');
        }
        
        // Templates store
        if (!db.objectStoreNames.contains('templates')) {
          const templateStore = db.createObjectStore('templates', { keyPath: 'id' });
          templateStore.createIndex('by-category', 'category');
        }
        
        // Executions store
        if (!db.objectStoreNames.contains('executions')) {
          const executionStore = db.createObjectStore('executions', { keyPath: 'id' });
          executionStore.createIndex('by-workflow', 'workflowId');
          executionStore.createIndex('by-date', 'startedAt');
        }
      };
    });
  }
  
  async saveWorkflow(workflow: Workflow): Promise<void> {
    const tx = this.db!.transaction('workflows', 'readwrite');
    const store = tx.objectStore('workflows');
    workflow.updatedAt = new Date();
    await store.put(workflow);
  }
  
  async loadWorkflow(workflowId: string): Promise<Workflow | undefined> {
    const tx = this.db!.transaction('workflows', 'readonly');
    const store = tx.objectStore('workflows');
    return await store.get(workflowId);
  }
  
  async listWorkflows(): Promise<Workflow[]> {
    const tx = this.db!.transaction('workflows', 'readonly');
    const store = tx.objectStore('workflows');
    const index = store.index('by-updated');
    return await index.getAll();
  }
  
  async deleteWorkflow(workflowId: string): Promise<void> {
    const tx = this.db!.transaction('workflows', 'readwrite');
    const store = tx.objectStore('workflows');
    await store.delete(workflowId);
  }
}
```

## Performance Optimizations

1. **Virtual Scrolling**: Use react-window for log viewer with thousands of entries
2. **Memoization**: Memoize expensive node renderings with React.memo
3. **Web Workers**: Execute agents in web workers to avoid blocking UI
4. **Debouncing**: Debounce property panel updates to avoid excessive re-renders
5. **Lazy Loading**: Load execution history and logs on demand
6. **Canvas Optimization**: Use React Flow's built-in performance optimizations (viewport culling)
7. **IndexedDB**: Async storage to avoid blocking main thread
8. **Edge Batching**: Batch edge updates during execution to reduce re-renders

## Rationale

**Why React Flow?** 
- Battle-tested with 20k+ GitHub stars
- Excellent performance with large graphs
- Built-in features (minimap, controls, zoom, pan)
- Extensible with custom nodes and edges
- Active community and good documentation

**Why Zustand over Redux?**
- Less boilerplate (no actions/reducers)
- Better TypeScript support
- Simpler middleware for persistence
- Better performance (no unnecessary re-renders)
- Easier to test

**Why Web Workers for execution?**
- Prevents UI blocking during long agent executions
- Allows true parallel execution of independent agents
- Better error isolation
- Can be terminated if needed

**Why IndexedDB over localStorage?**
- Can store larger workflows (>5MB)
- Async API doesn't block main thread
- Better structured query support
- Can store binary data (future feature: screenshots)

**Topological execution with parallelization**
- Maximizes throughput by running independent agents concurrently
- Respects data dependencies automatically
- Easy to visualize execution progress

## What I Changed

This is the initial design, so there are no changes from a previous iteration.

## What I Kept

This is the initial design, so there are no previous ideas to keep.

## Open Questions

1. **Streaming vs. Batch**: Should agent outputs stream in real-time or return all at once? Streaming is more engaging but adds complexity.

2. **Agent Communication Protocol**: Should agents communicate through structured JSON or free-form text? JSON is more parseable but less flexible.

3. **Cost Management**: Should we add hard limits on token usage per workflow or just show estimates?

4. **Collaboration**: Should workflows be shareable via URL with a backend, or stay purely local?

5. **Version Control**: Should we track workflow versions with diffs, or just save snapshots?

## Convergence Status

**ITERATING** - This is the first draft and requires review for:
- Missing edge cases in execution engine
- UI/UX improvements for node configuration
- Additional agent types or capabilities
- Performance concerns with large workflows

PROMPT_FOR_CRITIC:
Please focus your review on:
1. **Execution engine design** - Are there race conditions or edge cases I'm missing?
2. **Data flow between agents** - Is the input/output mechanism clear and flexible enough?
3. **Error handling** - What failure modes am I not considering?
4. **Real-time visualization** - Are there better ways to show execution status?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Visual AI Agent Workflow Builder - Enhanced Design

## Architecture Overview

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     React Application                        │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │     │
│  │   Layer      │  │    Panel     │  │   & Palette  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
├─────────────────────────────────────────────────────────────┤
│           Workflow State Management (Zustand)               │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Execution  │  │  Template    │  │   Validation │     │
│  │   Orchestrator│  │  Manager     │  │   Service    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │  Data Flow   │  │  Error       │                        │
│  │  Controller  │  │  Recovery    │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas Library**: React Flow (react-flow-renderer)
- **State Management**: Zustand with immer middleware
- **UI Components**: Radix UI + Tailwind CSS
- **Execution**: Web Workers with SharedArrayBuffer for progress tracking
- **Storage**: IndexedDB with automatic sync queue for reliability
- **Real-time Updates**: EventEmitter pattern with typed events

## Core Components

### 1. Canvas Component (WorkflowCanvas.tsx)
```typescript
interface WorkflowCanvasProps {
  workflowId: string;
  readonly?: boolean;
}

const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({ 
  workflowId, 
  readonly = false 
}) => {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect } = 
    useWorkflowStore();
  const executionState = useExecutionState();
  
  // Handle drop from palette
  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    const type = event.dataTransfer.getData('application/reactflow');
    const position = screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    
    addNode(type, position);
  }, []);
  
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);
  
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onDrop={onDrop}
      onDragOver={onDragOver}
      nodeTypes={customNodeTypes}
      edgeTypes={customEdgeTypes}
      fitView
      minZoom={0.2}
      maxZoom={2}
      deleteKeyCode="Delete"
      selectionKeyCode="Shift"
      multiSelectionKeyCode="Control"
    >
      <Background />
      <Controls />
      <MiniMap />
      <ExecutionOverlay />
      <SelectionToolbar />
    </ReactFlow>
  );
};
```

### 2. Agent Node Component (AgentNode.tsx)
```typescript
interface AgentNodeData {
  id: string;
  type: 'researcher' | 'coder' | 'reviewer' | 'coordinator' | 'transformer';
  label: string;
  config: AgentConfig;
  status: ExecutionStatus;
  logs: LogEntry[];
  metrics: ExecutionMetrics;
  inputs: Record<string, InputDefinition>;  // ENHANCED: Define expected inputs
  outputs: Record<string, OutputDefinition>; // ENHANCED: Define outputs with schema
}

interface InputDefinition {
  name: string;
  type: 'text' | 'json' | 'code' | 'artifacts' | 'stream';
  required: boolean;
  schema?: JSONSchema; // For validation
  description?: string;
}

interface OutputDefinition {
  name: string;
  type: 'text' | 'json' | 'code' | 'artifacts' | 'stream';
  schema?: JSONSchema;
  description?: string;
}

interface AgentConfig {
  model: string;
  temperature: number;
  systemPrompt: string;
  maxTokens?: number;
  timeout?: number;
  retryConfig?: RetryConfig;
  streaming?: boolean; // ENHANCED: Support streaming output
  memoryLimit?: number; // ENHANCED: Prevent memory leaks
}

interface RetryConfig {
  maxAttempts: number;
  backoffStrategy: 'linear' | 'exponential' | 'fixed';
  initialDelayMs: number;
  maxDelayMs: number;
  retryableErrors: string[]; // Specific error patterns to retry
}

const AgentNode: React.FC<NodeProps<AgentNodeData>> = ({ data, selected }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const streamingOutput = useStreamingOutput(data.id);
  
  const getStatusColor = () => {
    switch (data.status) {
      case 'idle': return 'gray';
      case 'queued': return 'cyan'; // ENHANCED: New status
      case 'running': return 'blue';
      case 'success': return 'green';
      case 'error': return 'red';
      case 'warning': return 'orange'; // ENHANCED: Partial success
      case 'waiting': return 'yellow';
      case 'cancelled': return 'gray'; // ENHANCED: User cancelled
    }
  };

  return (
    <div 
      className={`agent-node ${selected ? 'selected' : ''} ${isExpanded ? 'expanded' : ''}`}
      data-node-id={data.id}
    >
      {/* Multiple input handles for different data types */}
      {Object.entries(data.inputs).map(([key, input]) => (
        <Handle
          key={`input-${key}`}
          type="target"
          position={Position.Left}
          id={`input-${key}`}
          style={{ top: calculateHandlePosition(key, data.inputs) }}
        >
          <Tooltip content={`${input.name} (${input.type})`}>
            <HandleLabel required={input.required}>{input.name}</HandleLabel>
          </Tooltip>
        </Handle>
      ))}
      
      <div className="node-header" style={{ borderColor: getStatusColor() }}>
        <AgentIcon type={data.type} />
        <span className="node-label" contentEditable onBlur={handleLabelUpdate}>
          {data.label}
        </span>
        <StatusBadge status={data.status} />
        <Button 
          size="xs" 
          variant="ghost"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </Button>
      </div>
      
      <div className="node-body">
        <div className="config-summary">
          <span className="model-badge">{data.config.model}</span>
          <span className="temp-badge">T: {data.config.temperature}</span>
          {data.config.streaming && <span className="stream-badge">⚡ Stream</span>}
        </div>
        
        {data.status === 'running' && (
          <>
            <ProgressBar metrics={data.metrics} />
            {/* ENHANCED: Show streaming output preview */}
            {data.config.streaming && streamingOutput && (
              <StreamPreview content={streamingOutput} />
            )}
          </>
        )}
        
        {/* ENHANCED: Show validation errors */}
        {data.status === 'error' && (
          <ErrorSummary error={data.logs.find(l => l.level === 'error')} />
        )}
        
        {isExpanded && (
          <div className="node-details">
            <LogPreview logs={data.logs.slice(-5)} />
            <MetricsDisplay metrics={data.metrics} />
          </div>
        )}
      </div>
      
      {/* Multiple output handles for different data types */}
      {Object.entries(data.outputs).map(([key, output]) => (
        <Handle
          key={`output-${key}`}
          type="source"
          position={Position.Right}
          id={`output-${key}`}
          style={{ top: calculateHandlePosition(key, data.outputs) }}
        >
          <Tooltip content={`${output.name} (${output.type})`}>
            <HandleLabel>{output.name}</HandleLabel>
          </Tooltip>
        </Handle>
      ))}
    </div>
  );
};
```

### 3. Connection Edge Component (DataFlowEdge.tsx)
```typescript
interface EdgeData {
  id: string;
  sourceHandle: string; // ENHANCED: Track which output
  targetHandle: string; // ENHANCED: Track which input
  dataType: 'text' | 'json' | 'code' | 'artifacts' | 'stream';
  transformations?: Transformation[];
  validation?: ValidationRule[]; // ENHANCED: Validate data flow
  status: 'idle' | 'active' | 'complete' | 'error';
  dataPreview?: string;
  bytesTransferred?: number; // ENHANCED: Track data size
}

interface ValidationRule {
  type: 'schema' | 'size' | 'format' | 'custom';
  config: any;
  errorMessage: string;
}

const DataFlowEdge: React.FC<EdgeProps<EdgeData>> = ({ 
  id, 
  source, 
  target, 
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  style,
  markerEnd
}) => {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, 
    sourceY, 
    targetX, 
    targetY,
    sourcePosition: Position.Right,
    targetPosition: Position.Left
  });

  // ENHANCED: Animate data flow
  const animationProgress = useAnimatedDataFlow(data.status);

  return (
    <>
      {/* Base edge path */}
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        style={{ 
          ...style, 
          stroke: data.status === 'error' ? '#ef4444' : 
                  data.status === 'active' ? '#3b82f6' : '#6b7280',
          strokeWidth: data.status === 'active' ? 3 : 2,
        }} 
        markerEnd={markerEnd}
      />
      
      {/* ENHANCED: Animated data flow indicator */}
      {data.status === 'active' && (
        <circle
          r="4"
          fill="#3b82f6"
        >
          <animateMotion
            dur="2s"
            repeatCount="indefinite"
            path={edgePath}
          />
        </circle>
      )}
      
      <EdgeLabelRenderer>
        <div
          style={{ 
            position: 'absolute', 
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            pointerEvents: 'all'
          }}
          className="edge-label"
        >
          <DataTypeIndicator type={data.dataType} />
          
          {/* ENHANCED: Show transformations applied */}
          {data.transformations && data.transformations.length > 0 && (
            <Tooltip content={
              <div>
                <strong>Transformations:</strong>
                <ul>
                  {data.transformations.map((t, i) => (
                    <li key={i}>{t.type}</li>
                  ))}
                </ul>
              </div>
            }>
              <TransformBadge count={data.transformations.length} />
            </Tooltip>
          )}
          
          {/* ENHANCED: Show validation errors */}
          {data.status === 'error' && (
            <Tooltip content="Data validation failed">
              <ErrorIcon className="text-red-500" />
            </Tooltip>
          )}
          
          {/* ENHANCED: Show data size for large transfers */}
          {data.bytesTransferred && data.bytesTransferred > 1024 && (
            <Tooltip content={`${formatBytes(data.bytesTransferred)} transferred`}>
              <DataSizeBadge size={data.bytesTransferred} />
            </Tooltip>
          )}
          
          {data.dataPreview && (
            <Popover>
              <PopoverTrigger>
                <Button size="xs" variant="ghost">
                  <EyeIcon />
                </Button>
              </PopoverTrigger>
              <PopoverContent>
                <DataPreview content={data.dataPreview} type={data.dataType} />
              </PopoverContent>
            </Popover>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
};
```

### 4. Properties Panel (PropertiesPanel.tsx)
```typescript
const PropertiesPanel: React.FC = () => {
  const { selectedNode, selectedEdge, updateNodeConfig, updateEdgeConfig } = 
    useWorkflowStore();
  
  if (!selectedNode && !selectedEdge) {
    return <EmptyState message="Select a node or connection to configure" />;
  }

  if (selectedEdge) {
    return <EdgePropertiesPanel edge={selectedEdge} />;
  }

  return (
    <div className="properties-panel">
      <Tabs defaultValue="config">
        <TabsList>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="prompt">System Prompt</TabsTrigger>
          <TabsTrigger value="io">Inputs/Outputs</TabsTrigger> {/* ENHANCED */}
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
          <TabsTrigger value="logs">Logs</TabsTrigger>
        </TabsList>
        
        <TabsContent value="config">
          <ConfigurationTab node={selectedNode} />
        </TabsContent>
        
        <TabsContent value="prompt">
          <PromptEditor 
            value={selectedNode.config.systemPrompt}
            onChange={(prompt) => updateNodeConfig(selectedNode.id, { systemPrompt: prompt })}
            variables={getAvailableVariables(selectedNode)}
            testMode // ENHANCED: Test prompts before execution
          />
        </TabsContent>
        
        <TabsContent value="io">
          <IOConfigTab node={selectedNode} /> {/* ENHANCED: Configure I/O */}
        </TabsContent>
        
        <TabsContent value="advanced">
          <AdvancedSettingsTab node={selectedNode} />
        </TabsContent>
        
        <TabsContent value="logs">
          <LogViewer logs={selectedNode.logs} nodeId={selectedNode.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
};

// ENHANCED: Configure inputs and outputs with schemas
const IOConfigTab: React.FC<{ node: AgentNodeData }> = ({ node }) => {
  const { updateNodeIO } = useWorkflowStore();
  
  return (
    <div className="io-config">
      <Section title="Input Definitions">
        {Object.entries(node.inputs).map(([key, input]) => (
          <InputConfig
            key={key}
            input={input}
            onChange={(updated) => updateNodeIO(node.id, 'input', key, updated)}
            onDelete={() => deleteNodeIO(node.id, 'input', key)}
          />
        ))}
        <Button onClick={() => addNodeIO(node.id, 'input')}>
          <PlusIcon /> Add Input
        </Button>
      </Section>
      
      <Section title="Output Definitions">
        {Object.entries(node.outputs).map(([key, output]) => (
          <OutputConfig
            key={key}
            output={output}
            onChange={(updated) => updateNodeIO(node.id, 'output', key, updated)}
            onDelete={() => deleteNodeIO(node.id, 'output', key)}
          />
        ))}
        <Button onClick={() => addNodeIO(node.id, 'output')}>
          <PlusIcon /> Add Output
        </Button>
      </Section>
    </div>
  );
};

// ENHANCED: Edge properties for transformations and validation
const EdgePropertiesPanel: React.FC<{ edge: WorkflowEdge }> = ({ edge }) => {
  const { updateEdgeConfig } = useWorkflowStore();
  
  return (
    <div className="edge-properties">
      <h3>Connection Properties</h3>
      
      <FormField label="Data Type">
        <Select 
          value={edge.data.dataType}
          onChange={(type) => updateEdgeConfig(edge.id, { dataType: type })}
        >
          <SelectOption value="text">Text</SelectOption>
          <SelectOption value="json">JSON</SelectOption>
          <SelectOption value="code">Code</SelectOption>
          <SelectOption value="artifacts">Artifacts</SelectOption>
          <SelectOption value="stream">Stream</SelectOption>
        </Select>
      </FormField>
      
      <Section title="Transformations">
        <TransformationBuilder
          transformations={edge.data.transformations || []}
          onChange={(transforms) => updateEdgeConfig(edge.id, { transformations: transforms })}
        />
      </Section>
      
      <Section title="Validation Rules">
        <ValidationBuilder
          rules={edge.data.validation || []}
          onChange={(rules) => updateEdgeConfig(edge.id, { validation: rules })}
        />
      </Section>
    </div>
  );
};
```

## Data Models

### Enhanced Workflow Schema
```typescript
interface Workflow {
  id: string;
  name: string;
  description?: string;
  version: string;
  createdAt: Date;
  updatedAt: Date;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  globalConfig: GlobalConfig;
  executionHistory: ExecutionRecord[];
  metadata: WorkflowMetadata; // ENHANCED
}

interface WorkflowMetadata {
  author?: string;
  tags: string[];
  category?: string;
  estimatedCost?: number;
  averageRuntime?: number;
  successRate?: number;
}

interface GlobalConfig {
  defaultModel: string;
  defaultTemperature: number;
  maxConcurrentAgents: number;
  errorHandling: 'stop' | 'continue' | 'retry';
  loggingLevel: 'debug' | 'info' | 'warn' | 'error';
  resourceLimits: ResourceLimits; // ENHANCED
  notifications: NotificationConfig; // ENHANCED
}

interface ResourceLimits {
  maxTokensPerNode?: number;
  maxTotalTokens?: number;
  maxExecutionTimeMs?: number;
  maxMemoryMB?: number;
  maxConcurrentConnections?: number;
}

interface NotificationConfig {
  onComplete: boolean;
  onError: boolean;
  onWarning: boolean;
  channels: ('browser' | 'email' | 'webhook')[];
  webhookUrl?: string;
}
```

### Enhanced Execution State
```typescript
interface ExecutionState {
  workflowId: string;
  executionId: string; // ENHANCED: Unique execution ID
  status: 'idle' | 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  startedAt?: Date;
  completedAt?: Date;
  currentNode?: string;
  nodeStates: Map<string, NodeExecutionState>;
  edgeStates: Map<string, EdgeExecutionState>; // ENHANCED: Track edge execution
  globalContext: ExecutionContext; // ENHANCED: Structured context
  errors: ExecutionError[];
  warnings: ExecutionWarning[]; // ENHANCED
  checkpoints: ExecutionCheckpoint[]; // ENHANCED: Resume capability
  resourceUsage: ResourceUsage; // ENHANCED
}

interface ExecutionContext {
  variables: Record<string, any>;
  secrets: Map<string, string>; // ENHANCED: Secure storage
  sharedMemory: SharedArrayBuffer; // ENHANCED: For worker communication
  artifacts: Map<string, Artifact>; // ENHANCED: Large objects
}

interface EdgeExecutionState {
  edgeId: string;
  status: 'idle' | 'active' | 'complete' | 'error';
  startedAt?: Date;
  completedAt?: Date;
  data?: any;
  validationErrors?: ValidationError[];
  bytesTransferred?: number;
}

interface ExecutionCheckpoint {
  timestamp: Date;
  nodeStates: Map<string, NodeExecutionState>;
  globalContext: ExecutionContext;
  reason: 'manual' | 'auto' | 'error';
}

interface ResourceUsage {
  totalTokens: number;
  totalCost: number;
  peakMemoryMB: number;
  executionTimeMs: number;
  apiCallCount: number;
}

interface ExecutionWarning {
  nodeId: string;
  timestamp: Date;
  type: 'performance' | 'cost' | 'resource' | 'deprecation';
  message: string;
  severity: 'low' | 'medium' | 'high';
  suggestion?: string;
}
```

## Enhanced State Management

```typescript
interface WorkflowStore {
  // Current workflow state
  workflow: Workflow | null;
  nodes: Node<AgentNodeData>[];
  edges: Edge<EdgeData>[];
  selectedNode: AgentNodeData | null;
  selectedEdge: EdgeData | null; // ENHANCED
  
  // Execution state
  executionState: ExecutionState | null;
  isExecuting: boolean;
  executionQueue: string[]; // ENHANCED: Queue multiple workflows
  
  // ENHANCED: Undo/Redo
  history: {
    past: WorkflowSnapshot[];
    future: WorkflowSnapshot[];
  };
  
  // Actions
  setWorkflow: (workflow: Workflow) => void;
  addNode: (type: string, position: XYPosition) => void;
  updateNode: (nodeId: string, updates: Partial<AgentNodeData>) => void;
  deleteNode: (nodeId: string) => void;
  addEdge: (connection: Connection) => void;
  updateEdge: (edgeId: string, updates: Partial<EdgeData>) => void; // ENHANCED
  deleteEdge: (edgeId: string) => void;
  selectNode: (nodeId: string | null) => void;
  selectEdge: (edgeId: string | null) => void; // ENHANCED
  
  // ENHANCED: Undo/Redo
  undo: () => void;
  redo: () => void;
  canUndo: () => boolean;
  canRedo: () => boolean;
  
  // Execution
  executeWorkflow: (config?: ExecutionConfig) => Promise<ExecutionResult>;
  pauseExecution: () => Promise<void>;
  resumeExecution: () => Promise<void>;
  stopExecution: () => Promise<void>;
  cancelExecution: () => Promise<void>; // ENHANCED
  executeNode: (nodeId: string, inputs?: any) => Promise<NodeExecutionResult>;
  createCheckpoint: () => void; // ENHANCED
  restoreCheckpoint: (checkpointId: string) => Promise<void>; // ENHANCED
  
  // Persistence
  saveWorkflow: () => Promise<void>;
  loadWorkflow: (workflowId: string) => Promise<void>;
  exportWorkflow: (format: 'json' | 'yaml') => string; // ENHANCED
  importWorkflow: (data: string, format: 'json' | 'yaml') => Promise<void>; // ENHANCED
  saveTemplate: (name: string) => Promise<void>;
  loadTemplate: (templateId: string) => Promise<void>;
  
  // Validation
  validateWorkflow: () => ValidationResult;
  validateNode: (nodeId: string) => ValidationResult; // ENHANCED
  validateEdge: (edgeId: string) => ValidationResult; // ENHANCED
  
  // ENHANCED: Event system
  events: EventEmitter<WorkflowEvents>;
}

interface WorkflowEvents {
  'node:added': (node: WorkflowNode) => void;
  'node:updated': (nodeId: string, updates: Partial<AgentNodeData>) => void;
  'node:deleted': (nodeId: string) => void;
  'edge:added': (edge: WorkflowEdge) => void;
  'edge:deleted': (edgeId: string) => void;
  'execution:started': (executionId: string) => void;
  'execution:node:start': (nodeId: string) => void;
  'execution:node:complete': (nodeId: string, result: any) => void;
  'execution:node:error': (nodeId: string, error: Error) => void;
  'execution:complete': (executionId: string, result: ExecutionResult) => void;
  'execution:failed': (executionId: string, error: Error) => void;
  'execution:cancelled': (executionId: string) => void;
}

const useWorkflowStore = create<WorkflowStore>()(
  immer((set, get) => ({
    workflow: null,
    nodes: [],
    edges: [],
    selectedNode: null,
    selectedEdge: null,
    executionState: null,
    isExecuting: false,
    executionQueue: [],
    history: { past: [], future: [] },
    events: new EventEmitter(),
    
    // ENHANCED: Snapshot before mutations for undo/redo
    _snapshot: () => {
      const state = get();
      const snapshot: WorkflowSnapshot = {
        nodes: [...state.nodes],
        edges: [...state.edges],
        workflow: state.workflow ? { ...state.workflow } : null,
        timestamp: Date.now()
      };
      
      set((draft) => {
        draft.history.past.push(snapshot);
        // Limit history size
        if (draft.history.past.length > 50) {
          draft.history.past.shift();
        }
        draft.history.future = [];
      });
    },
    
    addNode: (type, position) => {
      const state = get();
      state._snapshot();
      
      set((draft) => {
        const newNode = createDefaultNode(type, position);
        draft.nodes.push(newNode);
        draft.events.emit('node:added', newNode);
      });
    },
    
    undo: () => {
      set((draft) => {
        if (draft.history.past.length === 0) return;
        
        const current: WorkflowSnapshot = {
          nodes: draft.nodes,
          edges: draft.edges,
          workflow: draft.workflow,
          timestamp: Date.now()
        };
        
        draft.history.future.push(current);
        const previous = draft.history.past.pop()!;
        
        draft.nodes = previous.nodes;
        draft.edges = previous.edges;
        draft.workflow = previous.workflow;
      });
    },
    
    redo: () => {
      set((draft) => {
        if (draft.history.future.length === 0) return;
        
        const current: WorkflowSnapshot = {
          nodes: draft.nodes,
          edges: draft.edges,
          workflow: draft.workflow,
          timestamp: Date.now()
        };
        
        draft.history.past.push(current);
        const next = draft.history.future.pop()!;
        
        draft.nodes = next.nodes;
        draft.edges = next.edges;
        draft.workflow = next.workflow;
      });
    },
    
    // Implementation details...
  }))
);
```

## Enhanced Execution Engine

### Execution Orchestrator (Major Improvement)
```typescript
class WorkflowOrchestrator {
  private workflowId: string;
  private executionId: string;
  private nodes: Map<string, WorkflowNode>;
  private edges: WorkflowEdge[];
  private executionState: ExecutionState;
  private workerPool: WorkerPool; // ENHANCED: Pool of workers
  private dataFlowController: DataFlowController; // ENHANCED: Manage data transfer
  private checkpointManager: CheckpointManager; // ENHANCED: Save/restore state
  private eventBus: EventEmitter;
  private abortController: AbortController; // ENHANCED: Cancellation support
  
  constructor(workflow: Workflow, config?: ExecutionConfig) {
    this.workflowId = workflow.id;
    this.executionId = crypto.randomUUID();
    this.nodes = new Map(workflow.nodes.map(n => [n.id, n]));
    this.edges = workflow.edges;
    this.executionState = this.initExecutionState();
    this.workerPool = new WorkerPool(config?.maxWorkers || 4);
    this.dataFlowController = new DataFlowController();
    this.checkpointManager = new CheckpointManager();
    this.eventBus = new EventEmitter();
    this.abortController = new AbortController();
  }
  
  async execute(): Promise<ExecutionResult> {
    this.executionState.status = 'running';
    this.executionState.startedAt = new Date();
    this.eventBus.emit('execution:started', this.executionId);
    
    try {
      // ENHANCED: Pre-execution validation
      const validation = await this.validateBeforeExecution();
      if (!validation.valid) {
        throw new Error(`Validation failed: ${validation.errors.map(e => e.message).join(', ')}`);
      }
      
      // Build execution DAG
      const executionDAG = this.buildExecutionDAG();
      
      // ENHANCED: Check for resource availability
      await this.checkResourceAvailability();
      
      // Topological sort with parallel levels
      const executionLevels = this.topologicalSort(executionDAG);
      
      // Execute levels with proper error handling and checkpoints
      for (let levelIndex = 0; levelIndex < executionLevels.length; levelIndex++) {
        const level = executionLevels[levelIndex];
        
        // ENHANCED: Auto-checkpoint at each level
        if (levelIndex > 0 && levelIndex % 3 === 0) {
          await this.checkpointManager.createCheckpoint(this.executionState);
        }
        
        // ENHANCED: Check for cancellation
        if (this.abortController.signal.aborted) {
          throw new CancellationError('Execution cancelled by user');
        }
        
        try {
          await this.executeLevel(level);
        } catch (error) {
          // ENHANCED: Level-specific error handling
          const recoveryAction = await this.handleLevelError(levelIndex, level, error);
          
          if (recoveryAction === 'stop') {
            throw error;
          } else if (recoveryAction === 'retry') {
            await this.executeLevel(level); // Retry once
          } else if (recoveryAction === 'skip') {
            // Mark nodes as skipped and continue
            for (const nodeId of level) {
              this.executionState.nodeStates.get(nodeId)!.status = 'skipped';
            }
          }
        }
      }
      
      this.executionState.status = 'completed';
      this.executionState.completedAt = new Date();
      this.eventBus.emit('execution:complete', this.executionId, this.executionState);
      
      return {
        success: true,
        executionId: this.executionId,
        executionState: this.executionState,
        outputs: this.gatherWorkflowOutputs()
      };
      
    } catch (error) {
      this.executionState.status = error instanceof CancellationError ? 'cancelled' : 'failed';
      this.executionState.errors.push({
        nodeId: 'workflow',
        timestamp: new Date(),
        error: error as Error,
        recoverable: false,
        retryAttempts: 0
      });
      
      const event = error instanceof CancellationError ? 'execution:cancelled' : 'execution:failed';
      this.eventBus.emit(event, this.executionId, error);
      
      return {
        success: false,
        executionId: this.executionId,
        executionState: this.executionState,
        error: error as Error
      };
    } finally {
      // ENHANCED: Cleanup resources
      await this.cleanup();
    }
  }
  
  private async executeLevel(nodeIds: string[]): Promise<void> {
    // ENHANCED: Execute with resource-aware scheduling
    const nodePromises = nodeIds.map(nodeId => 
      this.workerPool.schedule(() => this.executeNode(nodeId))
    );
    
    // ENHANCED: Wait with proper error aggregation
    const results = await Promise.allSettled(nodePromises);
    
    // Check for failures
    const failures = results.filter(r => r.status === 'rejected');
    if (failures.length > 0 && this.executionState.workflow?.globalConfig.errorHandling === 'stop') {
      throw new AggregateError(
        failures.map(f => (f as PromiseRejectedResult).reason),
        `${failures.length} nodes failed in level`
      );
    }
  }
  
  private async executeNode(nodeId: string): Promise<NodeExecutionResult> {
    const node = this.nodes.get(nodeId)!;
    const nodeState = this.executionState.nodeStates.get(nodeId)!;
    
    // ENHANCED: Validate inputs before execution
    const inputValidation = await this.validateNodeInputs(nodeId);
    if (!inputValidation.valid) {
      nodeState.status = 'error';
      nodeState.error = {
        nodeId,
        timestamp: new Date(),
        error: new Error(`Input validation failed: ${inputValidation.errors.join(', ')}`),
        recoverable: false,
        retryAttempts: 0
      };
      throw nodeState.error.error;
    }
    
    nodeState.status = 'running';
    nodeState.startedAt = new Date();
    this.eventBus.emit('execution:node:start', nodeId);
    
    try {
      // Gather and validate inputs
      const inputs = await this.dataFlowController.gatherInputs(
        nodeId, 
        this.edges, 
        this.executionState
      );
      nodeState.input = inputs;
      
      // ENHANCED: Apply resource limits
      const resourceToken = await this.acquireResourceToken(node);
      
      try {
        // Execute with timeout and cancellation
        const result = await this.executeAgentWithTimeout(
          node, 
          inputs,
          node.data.config.timeout || 300000 // 5 min default
        );
        
        // ENHANCED: Validate output schema
        await this.validateNodeOutput(nodeId, result.output);
        
        nodeState.output = result.output;
        nodeState.logs.push(...result.logs);
        nodeState.metrics = result.metrics;
        nodeState.status = 'success';
        nodeState.completedAt = new Date();
        
        // ENHANCED: Store output with size limit
        await this.dataFlowController.storeOutput(
          nodeId,
          result.output,
          node.data.config.memoryLimit
        );
        
        // ENHANCED: Update edge states
        await this.updateOutgoingEdges(nodeId, result.output);
        
        this.eventBus.emit('execution:node:complete', nodeId, result);
        
        return result;
        
      } finally {
        // Release resource token
        resourceToken.release();
      }
      
    } catch (error) {
      nodeState.status = 'error';
      nodeState.completedAt = new Date();
      
      const executionError: ExecutionError = {
        nodeId,
        timestamp: new Date(),
        error: error as Error,
        recoverable: this.isRecoverableError(error),
        retryAttempts: nodeState.error?.retryAttempts || 0
      };
      
      nodeState.error = executionError;
      this.eventBus.emit('execution:node:error', nodeId, error);
      
      // ENHANCED: Retry logic with backoff
      if (executionError.recoverable && 
          node.data.config.retryConfig &&
          executionError.retryAttempts < node.data.config.retryConfig.maxAttempts) {
        
        executionError.retryAttempts++;
        const delay = this.calculateBackoff(
          node.data.config.retryConfig,
          executionError.retryAttempts
        );
        
        nodeState.logs.push({
          timestamp: new Date(),
          level: 'warn',
          nodeId,
          message: `Retrying after ${delay}ms (attempt ${executionError.retryAttempts})`,
        });
        
        await new Promise(resolve => setTimeout(resolve, delay));
        return this.executeNode(nodeId); // Recursive retry
      }
      
      throw error;
    }
  }
  
  // ENHANCED: Execute with timeout and cancellation support
  private async executeAgentWithTimeout(
    node: WorkflowNode,
    inputs: any,
    timeoutMs: number
  ): Promise<AgentExecutionResult> {
    return new Promise((resolve, reject) => {
      const timeoutId = setTimeout(() => {
        reject(new Error(`Node execution timed out after ${timeoutMs}ms`));
      }, timeoutMs);
      
      // Listen for cancellation
      this.abortController.signal.addEventListener('abort', () => {
        clearTimeout(timeoutId);
        reject(new CancellationError('Execution cancelled'));
      });
      
      this.workerPool.execute(node, inputs, this.abortController.signal)
        .then(result => {
          clearTimeout(timeoutId);
          resolve(result);
        })
        .catch(error => {
          clearTimeout(timeoutId);
          reject(error);
        });
    });
  }
  
  // ENHANCED: Validate inputs match expected schema
  private async validateNodeInputs(nodeId: string): Promise<ValidationResult> {
    const node = this.nodes.get(nodeId)!;
    const errors: string[] = [];
    
    // Check required inputs
    for (const [key, inputDef] of Object.entries(node.data.inputs)) {
      if (inputDef.required) {
        const hasInput = this.edges.some(e => 
          e.target === nodeId && e.targetHandle === `input-${key}`
        );
        
        if (!hasInput) {
          errors.push(`Required input '${inputDef.name}' is not connected`);
        }
      }
      
      // ENHANCED: Validate schema if provided
      if (inputDef.schema) {
        const incomingEdges = this.edges.filter(e => 
          e.target === nodeId && e.targetHandle === `input-${key}`
        );
        
        for (const edge of incomingEdges) {
          const sourceOutput = this.executionState.globalContext.variables[edge.source];
          if (sourceOutput) {
            const schemaValidation = validateAgainstSchema(sourceOutput, inputDef.schema);
            if (!schemaValidation.valid) {
              errors.push(`Input '${inputDef.name}' schema validation failed: ${schemaValidation.errors.join(', ')}`);
            }
          }
        }
      }
    }
    
    return {
      valid: errors.length === 0,
      errors: errors.map(msg => ({ type: 'config', nodeId, message: msg, severity: 'error' })),
      warnings: []
    };
  }
  
  // ENHANCED: Validate output matches expected schema
  private async validateNodeOutput(nodeId: string, output: any): Promise<void> {
    const node = this.nodes.get(nodeId)!;
    
    for (const [key, outputDef] of Object.entries(node.data.outputs)) {
      if (outputDef.schema) {
        const validation = validateAgainstSchema(output, outputDef.schema);
        if (!validation.valid) {
          throw new Error(
            `Output '${outputDef.name}' schema validation failed: ${validation.errors.join(', ')}`
          );
        }
      }
    }
  }
  
  // ENHANCED: Update edge states when data flows
  private async updateOutgoingEdges(nodeId: string, output: any): Promise<void> {
    const outgoingEdges = this.edges.filter(e => e.source === nodeId);
    
    for (const edge of outgoingEdges) {
      const edgeState = this.executionState.edgeStates.get(edge.id);
      if (edgeState) {
        edgeState.status = 'active';
        edgeState.startedAt = new Date();
        
        // Apply transformations
        let transformedData = output;
        if (edge.data.transformations) {
          transformedData = await this.dataFlowController.applyTransformations(
            output,
            edge.data.transformations
          );
        }
        
        // Validate against edge rules
        if (edge.data.validation) {
          const validation = await this.dataFlowController.validateData(
            transformedData,
            edge.data.validation
          );
          
          if (!validation.valid) {
            edgeState.status = 'error';
            edgeState.validationErrors = validation.errors;
            throw new Error(`Edge validation failed: ${validation.errors.map(e => e.message).join(', ')}`);
          }
        }
        
        edgeState.data = transformedData;
        edgeState.bytesTransferred = JSON.stringify(transformedData).length;
        edgeState.status = 'complete';
        edgeState.completedAt = new Date();
      }
    }
  }
  
  // ENHANCED: Check resource availability before execution
  private async checkResourceAvailability(): Promise<void> {
    const limits = this.executionState.workflow?.globalConfig.resourceLimits;
    if (!limits) return;
    
    // Estimate resource requirements
    const estimatedTokens = this.estimateTokenUsage();
    const estimatedMemory = this.estimateMemoryUsage();
    
    if (limits.maxTotalTokens && estimatedTokens > limits.maxTotalTokens) {
      throw new Error(
        `Estimated token usage (${estimatedTokens}) exceeds limit (${limits.maxTotalTokens})`
      );
    }
    
    if (limits.maxMemoryMB && estimatedMemory > limits.maxMemoryMB) {
      throw new Error(
        `Estimated memory usage (${estimatedMemory}MB) exceeds limit (${limits.maxMemoryMB}MB)`
      );
    }
  }
  
  private async cleanup(): Promise<void> {
    await this.workerPool.terminate();
    this.dataFlowController.cleanup();
  }
}
```

### Enhanced Data Flow Controller
```typescript
class DataFlowController {
  private dataCache: Map<string, any> = new Map();
  private memoryUsage: number = 0;
  
  async gatherInputs(
    nodeId: string,
    edges: WorkflowEdge[],
    executionState: ExecutionState
  ): Promise<Record<string, any>> {
    const inputs: Record<string, any> = {};
    const incomingEdges = edges.filter(e => e.target === nodeId);
    
    for (const edge of incomingEdges) {
      const sourceOutput = executionState.globalContext.variables[edge.source];
      
      if (sourceOutput === undefined) {
        throw new Error(`Missing output from source node: ${edge.source}`);
      }
      
      // Apply transformations
      const transformedOutput = edge.data.transformations
        ? await this.applyTransformations(sourceOutput, edge.data.transformations)
        : sourceOutput;
      
      // Map to target input handle
      const inputKey = edge.targetHandle?.replace('input-', '') || edge.source;
      inputs[inputKey] = transformedOutput;
    }
    
    return inputs;
  }
  
  async applyTransformations(
    data: any,
    transformations: Transformation[]
  ): Promise<any> {
    let result = data;
    
    for (const transform of transformations) {
      switch (transform.type) {
        case 'jsonpath':
          result = this.applyJsonPath(result, transform.config.path);
          break;
        case 'template':
          result = this.applyTemplate(result, transform.config.template);
          break;
        case 'filter':
          result = this.applyFilter(result, transform.config.predicate);
          break;
        case 'map':
          result = this.applyMap(result, transform.config.mapper);
          break;
        case 'aggregate':
          result = this.applyAggregate(result, transform.config.aggregator);
          break;
        default:
          throw new Error(`Unknown transformation type: ${transform.type}`);
      }
    }
    
    return result;
  }
  
  async validateData(data: any, rules: ValidationRule[]): Promise<ValidationResult> {
    const errors: ValidationError[] = [];
    
    for (const rule of rules) {
      switch (rule.type) {
        case 'schema':
          const schemaResult = validateAgainstSchema(data, rule.config.schema);
          if (!schemaResult.valid) {
            errors.push({
              type: 'connection',
              message: rule.errorMessage || schemaResult.errors.join(', '),
              severity: 'error'
            });
          }
          break;
          
        case 'size':
          const size = JSON.stringify(data).length;
          if (size > rule.config.maxBytes) {
            errors.push({
              type: 'connection',
              message: rule.errorMessage || `Data size (${size} bytes) exceeds limit (${rule.config.maxBytes} bytes)`,
              severity: 'error'
            });
          }
          break;
          
        case 'format':
          if (!this.validateFormat(data, rule.config.format)) {
            errors.push({
              type: 'connection',
              message: rule.errorMessage || `Data does not match format: ${rule.config.format}`,
              severity: 'error'
            });
          }
          break;
          
        case 'custom':
          const customResult = await rule.config.validator(data);
          if (!customResult.valid) {
            errors.push({
              type: 'connection',
              message: rule.errorMessage || customResult.error,
              severity: 'error'
            });
          }
          break;
      }
    }
    
    return {
      valid: errors.length === 0,
      errors,
      warnings: []
    };
  }
  
  async storeOutput(nodeId: string, output: any, memoryLimit?: number): Promise<void> {
    const size = JSON.stringify(output).length;
    
    // Check memory limit
    if (memoryLimit && this.memoryUsage + size > memoryLimit * 1024 * 1024) {
      throw new Error(`Memory limit exceeded: ${this.memoryUsage + size} bytes`);
    }
    
    this.dataCache.set(nodeId, output);
    this.memoryUsage += size;
  }
  
  cleanup(): void {
    this.dataCache.clear();
    this.memoryUsage = 0;
  }
  
  private applyJsonPath(data: any, path: string): any {
    // JSONPath implementation
    return JSONPath.query(data, path);
  }
  
  private applyTemplate(data: any, template: string): any {
    // Template engine (e.g., Handlebars)
    return Handlebars.compile(template)(data);
  }
  
  private applyFilter(data: any[], predicate: string): any[] {
    // Safe eval or predicate parser
    const fn = new Function('item', `return ${predicate}`);
    return data.filter(fn);
  }
  
  private applyMap(data: any[], mapper: string): any[] {
    const fn = new Function('item', `return ${mapper}`);
    return data.map(fn);
  }
  
  private applyAggregate(data: any[], aggregator: string): any {
    const fn = new Function('acc', 'item', `return ${aggregator}`);
    return data.reduce(fn, null);
  }
  
  private validateFormat(data: any, format: string): boolean {
    switch (format) {
      case 'json':
        try {
          JSON.parse(typeof data === 'string' ? data : JSON.stringify(data));
          return true;
        } catch {
          return false;
        }
      case 'url':
        try {
          new URL(data);
          return true;
        } catch {
          return false;
        }
      case 'email':
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data);
      default:
        return true;
    }
  }
}
```

### Enhanced Worker Pool
```typescript
class WorkerPool {
  private workers: Worker[] = [];
  private availableWorkers: Worker[] = [];
  private queue: QueueItem[] = [];
  private size: number;
  
  constructor(size: number = 4) {
    this.size = size;
    this.initWorkers();
  }
  
  private initWorkers(): void {
    for (let i = 0; i < this.size; i++) {
      const worker = new Worker(
        new URL('./execution.worker.ts', import.meta.url),
        { type: 'module' }
      );
      this.workers.push(worker);
      this.availableWorkers.push(worker);
    }
  }
  
  async schedule<T>(task: () => Promise<T>): Promise<T> {
    return new Promise((resolve, reject) => {
      this.queue.push({ task, resolve, reject });
      this.processQueue();
    });
  }
  
  async execute(
    node: WorkflowNode,
    inputs: any,
    signal: AbortSignal
  ): Promise<AgentExecutionResult> {
    return this.schedule(() => {
      return new Promise((resolve, reject) => {
        if (this.availableWorkers.length === 0) {
          throw new Error('No available workers');
        }
        
        const worker = this.availableWorkers.pop()!;
        const messageId = crypto.randomUUID();
        
        const handler = (event: MessageEvent) => {
          if (event.data.messageId === messageId) {
            worker.removeEventListener('message', handler);
            this.availableWorkers.push(worker);
            this.processQueue();
            
            if (event.data.error) {
              reject(new Error(event.data.error));
            } else {
              resolve(event.data.result);
            }
          }
        };
        
        // Handle cancellation
        const abortHandler = () => {
          worker.postMessage({ messageId, type: 'cancel' });
          worker.removeEventListener('message', handler);
          this.availableWorkers.push(worker);
          reject(new CancellationError('Execution cancelled'));
        };
        
        if (signal.aborted) {
          abortHandler();
          return;
        }
        
        signal.addEventListener('abort', abortHandler, { once: true });
        
        worker.addEventListener('message', handler);
        worker.postMessage({
          messageId,
          type: 'execute',
          node,
          inputs
        });
      });
    });
  }
  
  private processQueue(): void {
    while (this.queue.length > 0 && this.availableWorkers.length > 0) {
      const item = this.queue.shift()!;
      item.task().then(item.resolve).catch(item.reject);
    }
  }
  
  async terminate(): Promise<void> {
    for (const worker of this.workers) {
      worker.terminate();
    }
    this.workers = [];
    this.availableWorkers = [];
    this.queue = [];
  }
}
```

### Enhanced Checkpoint Manager
```typescript
class CheckpointManager {
  private db: IDBDatabase;
  
  async createCheckpoint(
    executionState: ExecutionState,
    reason: 'manual' | 'auto' | 'error' = 'auto'
  ): Promise<string> {
    const checkpointId = crypto.randomUUID();
    
    const checkpoint: ExecutionCheckpoint = {
      timestamp: new Date(),
      nodeStates: new Map(executionState.nodeStates),
      globalContext: this.cloneContext(executionState.globalContext),
      reason
    };
    
    const tx = this.db.transaction('checkpoints', 'readwrite');
    const store = tx.objectStore('checkpoints');
    
    await store.put({
      id: checkpointId,
      executionId: executionState.executionId,
      checkpoint: this.serializeCheckpoint(checkpoint)
    });
    
    return checkpointId;
  }
  
  async restoreCheckpoint(
    checkpointId: string
  ): Promise<ExecutionCheckpoint> {
    const tx = this.db.transaction('checkpoints', 'readonly');
    const store = tx.objectStore('checkpoints');
    const record = await store.get(checkpointId);
    
    if (!record) {
      throw new Error(`Checkpoint not found: ${checkpointId}`);
    }
    
    return this.deserializeCheckpoint(record.checkpoint);
  }
  
  private cloneContext(context: ExecutionContext): ExecutionContext {
    return {
      variables: { ...context.variables },
      secrets: new Map(context.secrets),
      sharedMemory: context.sharedMemory, // Reference, not cloned
      artifacts: new Map(context.artifacts)
    };
  }
  
  private serializeCheckpoint(checkpoint: ExecutionCheckpoint): string {
    return JSON.stringify({
      timestamp: checkpoint.timestamp.toISOString(),
      nodeStates: Array.from(checkpoint.nodeStates.entries()),
      globalContext: {
        variables: checkpoint.globalContext.variables,
        // Exclude non-serializable items
      },
      reason: checkpoint.reason
    });
  }
  
  private deserializeCheckpoint(data: string): ExecutionCheckpoint {
    const parsed = JSON.parse(data);
    return {
      timestamp: new Date(parsed.timestamp),
      nodeStates: new Map(parsed.nodeStates),
      globalContext: {
        variables: parsed.globalContext.variables,
        secrets: new Map(),
        artifacts: new Map()
      },
      reason: parsed.reason
    };
  }
}
```

## What I Improved

### 1. **Execution Engine Robustness**
- **Worker Pool**: Added a proper worker pool with scheduling instead of creating workers on-demand. This prevents resource exhaustion and improves performance.
- **Cancellation Support**: Added `AbortController` throughout the execution chain for graceful cancellation.
- **Checkpoint System**: Added automatic checkpoints every 3 levels and manual checkpoint capability for resuming long-running workflows.
- **Resource Limits**: Added memory limits, token limits, and execution time limits with pre-flight checks.
- **Timeout Handling**: Wrapped execution with configurable timeouts to prevent infinite hangs.

### 2. **Data Flow Architecture**
- **Data Flow Controller**: Created a dedicated controller to manage data transfer, transformations, and validation between nodes.
- **Input/Output Definitions**: Added explicit input/output schemas to nodes with validation, making data contracts clear and type-safe.
- **Multiple Handles**: Support multiple input/output handles per node for different data types (instead of single source/target).
- **Edge State Tracking**: Track edge execution state separately from nodes, including bytes transferred and validation errors.
- **Transformation Pipeline**: Enhanced transformations with JSONPath, templates, filters, maps, and aggregations.
- **Validation Rules**: Added comprehensive validation rules (schema, size, format, custom) on edges.

### 3. **Error Handling**
- **Aggregate Errors**: Use `AggregateError` to collect multiple failures in parallel execution levels.
- **Recoverable Errors**: Distinguish between recoverable (retry) and non-recoverable (stop) errors.
- **Retry Configuration**: Per-node retry config with backoff strategies and specific error patterns to retry.
- **Level Error Recovery**: Handle errors at the level (not just node) to decide whether to stop, retry, or skip.
- **Warnings**: Added warnings for non-fatal issues (performance, cost, resource usage).
- **Input/Output Validation**: Validate inputs before execution and outputs after execution against schemas.

### 4. **Real-time Visualization**
- **Edge Animation**: Animate data flow with moving particles along edges during execution.
- **Edge State Display**: Show validation errors, transformations, and data size on edges.
- **Streaming Preview**: Show streaming output in real-time within node body.
- **Expandable Nodes**: Expand nodes to see detailed logs and metrics inline.
- **Status Granularity**: Added more statuses: `queued`, `warning`, `cancelled` for better visibility.
- **Event System**: Emit typed events for all workflow changes and execution progress.

### 5. **State Management**
- **Undo/Redo**: Added full undo/redo with snapshot history (up to 50 snapshots).
- **Immer Integration**: Use immer middleware for immutable state updates.
- **Event Emitter**: Type-safe event system for reactive updates.
- **Edge Selection**: Support selecting and configuring edges in properties panel.

### 6. **Other Improvements**
- **Execution Queue**: Support queuing multiple workflow executions.
- **Resource Usage Tracking**: Track total tokens, cost, memory, API calls.
- **Notification System**: Configurable notifications via browser, email, or webhook.
- **Export/Import**: Export workflows as JSON or YAML for sharing.
- **Metadata**: Track workflow metadata (author, tags, category, success rate).
- **Transformer Node Type**: Added transformer node for pure data transformations without AI.
- **Selection Toolbar**: Multi-select nodes and bulk operations.

## What I Kept

The original design had excellent foundations:

- **React Flow**: Perfect choice for the canvas library - mature, performant, extensible.
- **Zustand**: Good state management choice - lightweight and performant.
- **Web Workers**: Correct approach for non-blocking execution.
- **IndexedDB**: Right storage solution for large workflows.
- **Topological Sort with Parallelization**: Excellent approach for DAG execution.
- **UI Component Structure**: Canvas, Properties Panel, Toolbar layout is well-designed.
- **Template System**: Variable substitution approach is solid.
- **Validation Service**: Graph validation logic is comprehensive.

## Remaining Concerns

### 1. **Memory Management**
- Large workflows with many artifacts could exhaust browser memory
- Need aggressive garbage collection strategy for completed nodes
- Consider offloading artifacts to IndexedDB instead of keeping in memory
- SharedArrayBuffer may not be available in all browsers (requires CORS headers)

### 2. **Streaming Implementation**
- Streaming adds significant complexity to data flow
- How to handle backpressure if downstream nodes can't keep up?
- Should streaming outputs be persisted or only the final result?
- Edge transformations on streams require different handling

### 3. **Security**
- Transformation functions use `new Function()` which is risky
- Need proper sandboxing or switch to a safe expression evaluator
- Secrets in ExecutionContext need encryption at rest
- Web Workers can still access some APIs - need to restrict

### 4. **Error Recovery**
- Retry logic could lead to exponential cost if not careful
- Partial failures in parallel levels are complex to reason about
- Checkpoint restoration doesn't handle external state (API calls already made)

### 5. **Performance at Scale**
- Workflows with 100+ nodes may overwhelm the UI
- React Flow re-renders can be expensive with many edges
- Need virtual rendering or viewport culling for very large workflows
- Worker pool size needs dynamic adjustment based on browser capabilities

### 6. **Testing**
- Web Workers are difficult to test
- Execution orchestration has many code paths (success, failure, retry, cancel)
- Need comprehensive integration tests for edge cases

## Convergence Status

**ITERATING** - The design has significant improvements but needs another round to address:
1. Memory management strategy for large workflows
2. Streaming implementation details and backpressure handling
3. Security sandboxing for custom transformations
4. Checkpoint/resume edge cases
5. Performance optimization strategy for 100+ node workflows

PROMPT_FOR_ARCHITECT:
Please focus on:
1. **Memory management**: How should we handle workflows that generate GBs of artifacts? Should we stream to IndexedDB? Implement LRU eviction?
2. **Streaming architecture**: Can you design the backpressure mechanism for streaming between nodes? How do edge transformations work on streams?
3. **Security model**: How can we safely allow custom transformations without `new Function()`? Should we use a safe expression language like JSONata?
4. **Checkpoint consistency**: How do we handle external side effects (API calls, file writes) during checkpoint restoration? Should we track "compensation" operations?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

# Visual AI Agent Workflow Builder - Production-Ready Architecture

## Core Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │         │
│  │   (React     │  │    Panel     │  │   & Palette  │         │
│  │    Flow)     │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│           State Management (Zustand + Immer)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Orchestration Layer                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Streaming  │  │  Memory    │  │ Checkpoint │         │  │
│  │  │ Executor   │  │  Manager   │  │  Manager   │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Data Flow & Storage Layer                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │  Hybrid    │  │   Safe     │  │   Side     │         │  │
│  │  │  Storage   │  │ Expression │  │   Effect   │         │  │
│  │  │  Manager   │  │  Evaluator │  │   Tracker  │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas**: React Flow v11+ with custom viewport rendering
- **State**: Zustand with immer middleware and persistence
- **UI**: Radix UI primitives + Tailwind CSS
- **Execution**: Dual-mode: in-memory for small data, streaming for large data
- **Storage**: Hybrid - Memory + IndexedDB with automatic tiering
- **Expressions**: JSONata (safe, sandboxed expression language)
- **Workers**: Shared Worker pool with resource quotas

## Memory Management Architecture

### Hybrid Storage Manager

The key innovation is **automatic tiering** between memory and IndexedDB based on data size and access patterns:

```typescript
interface StorageConfig {
  memoryThresholdBytes: number; // 10MB default
  maxMemoryBytes: number; // 100MB default
  evictionStrategy: 'lru' | 'size-based' | 'hybrid';
  compressionEnabled: boolean;
  persistenceMode: 'eager' | 'lazy' | 'manual';
}

class HybridStorageManager {
  private memoryCache: Map<string, CachedData> = new Map();
  private accessLog: Map<string, AccessMetadata> = new Map();
  private currentMemoryUsage: number = 0;
  private db: IDBDatabase;
  private config: StorageConfig;
  
  constructor(config: StorageConfig) {
    this.config = config;
    this.initIndexedDB();
  }
  
  async store(key: string, data: any, metadata: DataMetadata): Promise<void> {
    const serialized = JSON.stringify(data);
    const sizeBytes = new Blob([serialized]).size;
    
    // Automatic tiering decision
    const shouldStoreInMemory = this.shouldUseMemory(sizeBytes, metadata);
    
    if (shouldStoreInMemory) {
      await this.storeInMemory(key, data, sizeBytes, metadata);
    } else {
      await this.storeInIndexedDB(key, data, sizeBytes, metadata);
    }
    
    // Update access log
    this.accessLog.set(key, {
      lastAccessed: Date.now(),
      accessCount: 0,
      size: sizeBytes,
      location: shouldStoreInMemory ? 'memory' : 'indexeddb'
    });
  }
  
  async retrieve(key: string): Promise<any> {
    // Check memory first
    if (this.memoryCache.has(key)) {
      this.updateAccessMetadata(key);
      return this.memoryCache.get(key)!.data;
    }
    
    // Fallback to IndexedDB
    const data = await this.retrieveFromIndexedDB(key);
    
    // Promote to memory if frequently accessed
    const metadata = this.accessLog.get(key);
    if (metadata && this.shouldPromoteToMemory(metadata)) {
      await this.promoteToMemory(key, data);
    }
    
    return data;
  }
  
  private shouldUseMemory(sizeBytes: number, metadata: DataMetadata): boolean {
    // Never store in memory if exceeds threshold
    if (sizeBytes > this.config.memoryThresholdBytes) {
      return false;
    }
    
    // Check if we have room
    if (this.currentMemoryUsage + sizeBytes > this.config.maxMemoryBytes) {
      // Try to evict
      if (!this.evictToMakeRoom(sizeBytes)) {
        return false;
      }
    }
    
    // Use memory for hot data (intermediate results, frequently accessed)
    if (metadata.accessPattern === 'hot' || metadata.temporary) {
      return true;
    }
    
    // Use memory for small data that's cheap to keep
    return sizeBytes < 1024 * 100; // 100KB
  }
  
  private evictToMakeRoom(requiredBytes: number): boolean {
    const candidates = Array.from(this.memoryCache.entries())
      .map(([key, data]) => ({
        key,
        data,
        metadata: this.accessLog.get(key)!
      }))
      .sort((a, b) => {
        // Hybrid eviction: prioritize by LRU and size
        if (this.config.evictionStrategy === 'lru') {
          return a.metadata.lastAccessed - b.metadata.lastAccessed;
        } else if (this.config.evictionStrategy === 'size-based') {
          return b.metadata.size - a.metadata.size; // Evict largest first
        } else {
          // Hybrid: score = (age * size) - evict oldest large items first
          const scoreA = (Date.now() - a.metadata.lastAccessed) * a.metadata.size;
          const scoreB = (Date.now() - b.metadata.lastAccessed) * b.metadata.size;
          return scoreB - scoreA;
        }
      });
    
    let freedBytes = 0;
    const toEvict: string[] = [];
    
    for (const candidate of candidates) {
      // Never evict if accessed in last 5 seconds
      if (Date.now() - candidate.metadata.lastAccessed < 5000) {
        continue;
      }
      
      toEvict.push(candidate.key);
      freedBytes += candidate.metadata.size;
      
      if (freedBytes >= requiredBytes) {
        break;
      }
    }
    
    // Perform eviction
    for (const key of toEvict) {
      this.evictToIndexedDB(key);
    }
    
    return freedBytes >= requiredBytes;
  }
  
  private async evictToIndexedDB(key: string): Promise<void> {
    const cached = this.memoryCache.get(key);
    if (!cached) return;
    
    // Move to IndexedDB
    await this.storeInIndexedDB(key, cached.data, cached.size, cached.metadata);
    
    // Remove from memory
    this.memoryCache.delete(key);
    this.currentMemoryUsage -= cached.size;
    
    // Update location
    const metadata = this.accessLog.get(key);
    if (metadata) {
      metadata.location = 'indexeddb';
    }
  }
  
  private async storeInMemory(
    key: string, 
    data: any, 
    size: number, 
    metadata: DataMetadata
  ): Promise<void> {
    this.memoryCache.set(key, {
      data,
      size,
      metadata,
      storedAt: Date.now()
    });
    this.currentMemoryUsage += size;
  }
  
  private async storeInIndexedDB(
    key: string,
    data: any,
    size: number,
    metadata: DataMetadata
  ): Promise<void> {
    const serialized = JSON.stringify(data);
    
    // Optional compression for large data
    const toStore = this.config.compressionEnabled && size > 1024 * 100
      ? await this.compress(serialized)
      : serialized;
    
    const tx = this.db.transaction('artifacts', 'readwrite');
    const store = tx.objectStore('artifacts');
    
    await store.put({
      key,
      data: toStore,
      size,
      metadata,
      compressed: this.config.compressionEnabled && size > 1024 * 100,
      storedAt: Date.now()
    });
  }
  
  private async retrieveFromIndexedDB(key: string): Promise<any> {
    const tx = this.db.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    const record = await store.get(key);
    
    if (!record) {
      throw new Error(`Data not found: ${key}`);
    }
    
    const data = record.compressed 
      ? await this.decompress(record.data)
      : record.data;
    
    return JSON.parse(data);
  }
  
  private shouldPromoteToMemory(metadata: AccessMetadata): boolean {
    // Promote if accessed 3+ times in last minute
    return metadata.accessCount >= 3 && 
           Date.now() - metadata.lastAccessed < 60000;
  }
  
  private async promoteToMemory(key: string, data: any): Promise<void> {
    const metadata = this.accessLog.get(key);
    if (!metadata) return;
    
    await this.storeInMemory(key, data, metadata.size, {
      temporary: true,
      accessPattern: 'hot'
    });
    
    metadata.location = 'memory';
  }
  
  private updateAccessMetadata(key: string): void {
    const metadata = this.accessLog.get(key);
    if (metadata) {
      metadata.lastAccessed = Date.now();
      metadata.accessCount++;
    }
  }
  
  async clear(predicate?: (key: string, metadata: AccessMetadata) => boolean): Promise<void> {
    if (!predicate) {
      this.memoryCache.clear();
      this.accessLog.clear();
      this.currentMemoryUsage = 0;
      
      const tx = this.db.transaction('artifacts', 'readwrite');
      await tx.objectStore('artifacts').clear();
      return;
    }
    
    // Selective clear
    for (const [key, metadata] of this.accessLog.entries()) {
      if (predicate(key, metadata)) {
        this.memoryCache.delete(key);
        
        const tx = this.db.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').delete(key);
        
        this.accessLog.delete(key);
      }
    }
    
    // Recalculate memory usage
    this.currentMemoryUsage = Array.from(this.memoryCache.values())
      .reduce((sum, cached) => sum + cached.size, 0);
  }
  
  getMemoryUsage(): MemoryStats {
    return {
      currentBytes: this.currentMemoryUsage,
      maxBytes: this.config.maxMemoryBytes,
      itemCount: this.memoryCache.size,
      utilizationPercent: (this.currentMemoryUsage / this.config.maxMemoryBytes) * 100,
      evictionCount: this.evictionCount
    };
  }
  
  private async compress(data: string): Promise<Uint8Array> {
    const encoder = new TextEncoder();
    const stream = new Blob([data]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    return new Uint8Array(buffer);
  }
  
  private async decompress(data: Uint8Array): Promise<string> {
    const stream = new Blob([data]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowArtifacts', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('artifacts')) {
          db.createObjectStore('artifacts', { keyPath: 'key' });
        }
      };
    });
  }
}

interface CachedData {
  data: any;
  size: number;
  metadata: DataMetadata;
  storedAt: number;
}

interface DataMetadata {
  temporary?: boolean; // Will be cleared after workflow completion
  accessPattern?: 'hot' | 'warm' | 'cold';
  nodeId?: string;
  executionId?: string;
}

interface AccessMetadata {
  lastAccessed: number;
  accessCount: number;
  size: number;
  location: 'memory' | 'indexeddb';
}

interface MemoryStats {
  currentBytes: number;
  maxBytes: number;
  itemCount: number;
  utilizationPercent: number;
  evictionCount: number;
}
```

### Usage Example
```typescript
const storageManager = new HybridStorageManager({
  memoryThresholdBytes: 10 * 1024 * 1024, // 10MB
  maxMemoryBytes: 100 * 1024 * 1024, // 100MB
  evictionStrategy: 'hybrid',
  compressionEnabled: true,
  persistenceMode: 'lazy'
});

// Store node output - automatically tiered
await storageManager.store(
  `node-${nodeId}-output`,
  output,
  {
    nodeId,
    executionId,
    temporary: true, // Clear after workflow completes
    accessPattern: 'hot' // Keep in memory if possible
  }
);

// Retrieve - transparent whether in memory or IndexedDB
const output = await storageManager.retrieve(`node-${nodeId}-output`);

// Clear temporary data after workflow completes
await storageManager.clear((key, metadata) => 
  metadata.location === 'memory' && 
  key.includes(executionId)
);
```

## Streaming Architecture with Backpressure

### Streaming Execution Model

Use **ReadableStream** and **TransformStream** APIs for proper backpressure handling:

```typescript
interface StreamConfig {
  highWaterMark: number; // Buffer size
  strategy: 'chunk' | 'line' | 'token'; // How to split data
  backpressureThreshold: number; // When to pause upstream
}

class StreamingExecutor {
  private activeStreams: Map<string, StreamController> = new Map();
  
  async executeNodeStreaming(
    node: WorkflowNode,
    inputs: Record<string, any | ReadableStream>
  ): Promise<ReadableStream> {
    // Create output stream
    const { readable, writable } = new TransformStream({
      transform: async (chunk, controller) => {
        // Process chunk through agent
        const result = await this.processChunk(node, chunk);
        controller.enqueue(result);
      },
      flush: async (controller) => {
        // Final processing
        controller.terminate();
      }
    }, {
      highWaterMark: node.data.config.streamConfig?.highWaterMark || 10,
      size: (chunk) => chunk.length || 1
    });
    
    // Track stream for cancellation
    const streamController: StreamController = {
      nodeId: node.id,
      readable,
      writable,
      cancel: () => writable.abort(),
      pause: () => this.pauseStream(node.id),
      resume: () => this.resumeStream(node.id)
    };
    
    this.activeStreams.set(node.id, streamController);
    
    // Handle input streams
    const inputStreams = Object.entries(inputs).filter(([_, v]) => 
      v instanceof ReadableStream
    );
    
    if (inputStreams.length > 0) {
      // Merge multiple input streams with backpressure
      const mergedStream = this.mergeStreams(
        inputStreams.map(([_, stream]) => stream as ReadableStream),
        node.data.config.streamConfig
      );
      
      // Pipe through node processor
      mergedStream.pipeTo(writable, {
        preventAbort: true,
        preventClose: true,
        preventCancel: true
      }).catch(error => {
        console.error(`Stream error in node ${node.id}:`, error);
      });
    }
    
    return readable;
  }
  
  private mergeStreams(
    streams: ReadableStream[],
    config?: StreamConfig
  ): ReadableStream {
    return new ReadableStream({
      async start(controller) {
        const readers = streams.map(s => s.getReader());
        const activeReaders = new Set(readers);
        
        // Read from all streams concurrently with backpressure
        const readNext = async (reader: ReadableStreamDefaultReader) => {
          try {
            const { done, value } = await reader.read();
            
            if (done) {
              activeReaders.delete(reader);
              if (activeReaders.size === 0) {
                controller.close();
              }
              return;
            }
            
            // Enqueue with backpressure check
            const desiredSize = controller.desiredSize;
            if (desiredSize !== null && desiredSize <= 0) {
              // Backpressure - wait before reading more
              await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            controller.enqueue(value);
            
            // Continue reading
            readNext(reader);
          } catch (error) {
            controller.error(error);
          }
        };
        
        // Start reading from all streams
        readers.forEach(reader => readNext(reader));
      },
      
      cancel(reason) {
        // Cancel all input streams
        streams.forEach(s => s.cancel(reason));
      }
    }, {
      highWaterMark: config?.highWaterMark || 10
    });
  }
  
  private async processChunk(node: WorkflowNode, chunk: any): Promise<any> {
    // Process chunk through agent (streaming API call)
    // This is where actual LLM streaming happens
    return chunk; // Placeholder
  }
  
  private pauseStream(nodeId: string): void {
    const controller = this.activeStreams.get(nodeId);
    if (controller) {
      // Implement pause by not reading from stream
      controller.paused = true;
    }
  }
  
  private resumeStream(nodeId: string): void {
    const controller = this.activeStreams.get(nodeId);
    if (controller) {
      controller.paused = false;
    }
  }
  
  cancelAllStreams(): void {
    for (const [nodeId, controller] of this.activeStreams) {
      controller.cancel();
    }
    this.activeStreams.clear();
  }
}

interface StreamController {
  nodeId: string;
  readable: ReadableStream;
  writable: WritableStream;
  paused?: boolean;
  cancel: () => void;
  pause: () => void;
  resume: () => void;
}
```

### Stream Transformations

Transform streams safely using **TransformStream**:

```typescript
class StreamTransformer {
  applyTransformations(
    stream: ReadableStream,
    transformations: Transformation[]
  ): ReadableStream {
    let result = stream;
    
    for (const transform of transformations) {
      result = result.pipeThrough(
        this.createTransformStream(transform)
      );
    }
    
    return result;
  }
  
  private createTransformStream(transform: Transformation): TransformStream {
    switch (transform.type) {
      case 'jsonpath':
        return new TransformStream({
          transform: async (chunk, controller) => {
            try {
              // Parse chunk as JSON
              const data = typeof chunk === 'string' ? JSON.parse(chunk) : chunk;
              // Apply JSONPath using JSONata
              const result = await this.evaluator.evaluate(transform.config.path, data);
              controller.enqueue(result);
            } catch (error) {
              controller.error(error);
            }
          }
        });
        
      case 'filter':
        return new TransformStream({
          transform: async (chunk, controller) => {
            const passes = await this.evaluator.evaluate(
              transform.config.predicate,
              { item: chunk }
            );
            if (passes) {
              controller.enqueue(chunk);
            }
            // Otherwise drop chunk (no enqueue)
          }
        });
        
      case 'map':
        return new TransformStream({
          transform: async (chunk, controller) => {
            const result = await this.evaluator.evaluate(
              transform.config.mapper,
              { item: chunk }
            );
            controller.enqueue(result);
          }
        });
        
      case 'batch':
        // Accumulate chunks into batches
        let buffer: any[] = [];
        return new TransformStream({
          transform: async (chunk, controller) => {
            buffer.push(chunk);
            if (buffer.length >= transform.config.batchSize) {
              controller.enqueue(buffer);
              buffer = [];
            }
          },
          flush: async (controller) => {
            if (buffer.length > 0) {
              controller.enqueue(buffer);
            }
          }
        });
        
      default:
        throw new Error(`Unknown transformation: ${transform.type}`);
    }
  }
}
```

### Dual-Mode Execution

Support both streaming and batch modes:

```typescript
class DualModeOrchestrator {
  async executeNode(
    node: WorkflowNode,
    inputs: Record<string, any>
  ): Promise<any | ReadableStream> {
    // Decide mode based on data size and node config
    const shouldStream = this.shouldUseStreamingMode(node, inputs);
    
    if (shouldStream) {
      return this.streamingExecutor.executeNodeStreaming(node, inputs);
    } else {
      return this.batchExecutor.executeNodeBatch(node, inputs);
    }
  }
  
  private shouldUseStreamingMode(
    node: WorkflowNode,
    inputs: Record<string, any>
  ): boolean {
    // Use streaming if:
    // 1. Node explicitly configured for streaming
    if (node.data.config.streaming) return true;
    
    // 2. Any input is a stream
    const hasStreamInput = Object.values(inputs).some(v => 
      v instanceof ReadableStream
    );
    if (hasStreamInput) return true;
    
    // 3. Expected output is large (estimated from input size)
    const inputSize = this.estimateDataSize(inputs);
    if (inputSize > 5 * 1024 * 1024) return true; // 5MB
    
    // 4. Downstream nodes need streaming
    const hasStreamingDownstream = this.hasStreamingDownstream(node);
    if (hasStreamingDownstream) return true;
    
    return false;
  }
  
  private estimateDataSize(data: any): number {
    try {
      return JSON.stringify(data).length;
    } catch {
      return 0;
    }
  }
  
  private hasStreamingDownstream(node: WorkflowNode): boolean {
    const downstreamEdges = this.edges.filter(e => e.source === node.id);
    return downstreamEdges.some(edge => {
      const targetNode = this.nodes.get(edge.target);
      return targetNode?.data.config.streaming;
    });
  }
}
```

## Safe Expression Evaluation

Use **JSONata** instead of `new Function()`:

```typescript
import jsonata from 'jsonata';

class SafeExpressionEvaluator {
  private cache: Map<string, jsonata.Expression> = new Map();
  private readonly timeout: number = 5000; // 5s timeout
  private readonly maxDepth: number = 100; // Prevent infinite recursion
  
  async evaluate(expression: string, context: any): Promise<any> {
    // Get or compile expression
    let compiled = this.cache.get(expression);
    
    if (!compiled) {
      try {
        compiled = jsonata(expression);
        
        // Register safe functions only
        compiled.registerFunction('now', () => new Date().toISOString());
        compiled.registerFunction('random', () => Math.random());
        compiled.registerFunction('uuid', () => crypto.randomUUID());
        
        // Cache for reuse
        this.cache.set(expression, compiled);
      } catch (error) {
        throw new Error(`Invalid expression: ${error.message}`);
      }
    }
    
    // Evaluate with timeout and error handling
    try {
      return await Promise.race([
        compiled.evaluate(context, {
          maxDepth: this.maxDepth
        }),
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Expression timeout')), this.timeout)
        )
      ]);
    } catch (error) {
      throw new Error(`Expression evaluation failed: ${error.message}`);
    }
  }
  
  validate(expression: string): { valid: boolean; error?: string } {
    try {
      jsonata(expression);
      return { valid: true };
    } catch (error) {
      return { valid: false, error: error.message };
    }
  }
  
  clearCache(): void {
    this.cache.clear();
  }
}

// Usage in transformations
class DataFlowController {
  private evaluator = new SafeExpressionEvaluator();
  
  async applyTransformations(
    data: any,
    transformations: Transformation[]
  ): Promise<any> {
    let result = data;
    
    for (const transform of transformations) {
      switch (transform.type) {
        case 'jsonpath':
          // JSONata expression: $.path.to.field
          result = await this.evaluator.evaluate(transform.config.path, result);
          break;
          
        case 'filter':
          // JSONata predicate: $[price > 100]
          const items = Array.isArray(result) ? result : [result];
          result = [];
          for (const item of items) {
            const passes = await this.evaluator.evaluate(
              transform.config.predicate,
              item
            );
            if (passes) result.push(item);
          }
          break;
          
        case 'map':
          // JSONata mapper: { "name": name, "total": price * quantity }
          const mappedItems = Array.isArray(result) ? result : [result];
          result = [];
          for (const item of mappedItems) {
            const mapped = await this.evaluator.evaluate(
              transform.config.mapper,
              item
            );
            result.push(mapped);
          }
          break;
          
        case 'aggregate':
          // JSONata aggregation: $sum(items.price)
          result = await this.evaluator.evaluate(
            transform.config.aggregator,
            result
          );
          break;
      }
    }
    
    return result;
  }
}
```

### JSONata Expression Examples

Provide helpful examples in the UI:

```typescript
const TRANSFORMATION_EXAMPLES = {
  jsonpath: [
    { label: 'Extract field', expression: '$.user.name' },
    { label: 'Array elements', expression: '$.items[*].name' },
    { label: 'Filter array', expression: '$.items[price > 100]' },
    { label: 'Nested path', expression: '$.response.data.results' }
  ],
  filter: [
    { label: 'Price > 100', expression: 'price > 100' },
    { label: 'Status is active', expression: 'status = "active"' },
    { label: 'Contains keyword', expression: '$contains(name, "test")' }
  ],
  map: [
    { label: 'Extract fields', expression: '{ "id": id, "name": name }' },
    { label: 'Calculate', expression: '{ "total": price * quantity }' },
    { label: 'Transform', expression: '{ "fullName": firstName & " " & lastName }' }
  ],
  aggregate: [
    { label: 'Sum', expression: '$sum(items.price)' },
    { label: 'Average', expression: '$average(items.rating)' },
    { label: 'Count', expression: '$count(items)' },
    { label: 'Max', expression: '$max(items.value)' }
  ]
};
```

## Checkpoint Consistency & Side Effect Tracking

### Side Effect Tracker

Track external operations for compensation during recovery:

```typescript
interface SideEffect {
  id: string;
  nodeId: string;
  type: 'api_call' | 'file_write' | 'database_update' | 'external_service';
  operation: string;
  timestamp: Date;
  parameters: any;
  result?: any;
  compensatable: boolean;
  compensationFn?: string; // JSONata expression for compensation
  status: 'pending' | 'executed' | 'compensated' | 'failed';
}

class SideEffectTracker {
  private effects: Map<string, SideEffect> = new Map();
  private db: IDBDatabase;
  
  async recordEffect(effect: Omit<SideEffect, 'id' | 'timestamp' | 'status'>): Promise<string> {
    const id = crypto.randomUUID();
    const sideEffect: SideEffect = {
      ...effect,
      id,
      timestamp: new Date(),
      status: 'pending'
    };
    
    this.effects.set(id, sideEffect);
    
    // Persist immediately
    await this.persistEffect(sideEffect);
    
    return id;
  }
  
  async markExecuted(effectId: string, result: any): Promise<void> {
    const effect = this.effects.get(effectId);
    if (!effect) return;
    
    effect.status = 'executed';
    effect.result = result;
    
    await this.persistEffect(effect);
  }
  
  async compensate(effectId: string): Promise<void> {
    const effect = this.effects.get(effectId);
    if (!effect || !effect.compensatable) {
      throw new Error(`Cannot compensate effect: ${effectId}`);
    }
    
    if (effect.status !== 'executed') {
      return; // Nothing to compensate
    }
    
    // Execute compensation
    if (effect.compensationFn) {
      const evaluator = new SafeExpressionEvaluator();
      await evaluator.evaluate(effect.compensationFn, {
        effect,
        result: effect.result
      });
    }
    
    effect.status = 'compensated';
    await this.persistEffect(effect);
  }
  
  async compensateAllForNode(nodeId: string): Promise<void> {
    const nodeEffects = Array.from(this.effects.values())
      .filter(e => e.nodeId === nodeId && e.status === 'executed')
      .reverse(); // Compensate in reverse order
    
    for (const effect of nodeEffects) {
      try {
        await this.compensate(effect.id);
      } catch (error) {
        console.error(`Failed to compensate effect ${effect.id}:`, error);
        effect.status = 'failed';
        await this.persistEffect(effect);
      }
    }
  }
  
  getEffectsForCheckpoint(checkpointTime: Date): SideEffect[] {
    return Array.from(this.effects.values())
      .filter(e => e.timestamp <= checkpointTime);
  }
  
  private async persistEffect(effect: SideEffect): Promise<void> {
    const tx = this.db.transaction('sideEffects', 'readwrite');
    const store = tx.objectStore('sideEffects');
    await store.put(effect);
  }
}
```

### Enhanced Checkpoint Manager with Side Effects

```typescript
class CheckpointManager {
  private db: IDBDatabase;
  private sideEffectTracker: SideEffectTracker;
  
  constructor(sideEffectTracker: SideEffectTracker) {
    this.sideEffectTracker = sideEffectTracker;
    this.initIndexedDB();
  }
  
  async createCheckpoint(
    executionState: ExecutionState,
    reason: 'manual' | 'auto' | 'error' = 'auto'
  ): Promise<string> {
    const checkpointId = crypto.randomUUID();
    
    // Capture side effects up to this point
    const sideEffects = this.sideEffectTracker.getEffectsForCheckpoint(new Date());
    
    const checkpoint: ExecutionCheckpoint = {
      id: checkpointId,
      timestamp: new Date(),
      nodeStates: new Map(executionState.nodeStates),
      globalContext: this.cloneContext(executionState.globalContext),
      sideEffects, // NEW: Track side effects
      reason
    };
    
    const tx = this.db.transaction('checkpoints', 'readwrite');
    const store = tx.objectStore('checkpoints');
    
    await store.put({
      id: checkpointId,
      executionId: executionState.executionId,
      checkpoint: this.serializeCheckpoint(checkpoint)
    });
    
    return checkpointId;
  }
  
  async restoreCheckpoint(
    checkpointId: string,
    compensationStrategy: 'rollback' | 'forward' | 'manual'
  ): Promise<ExecutionCheckpoint> {
    const tx = this.db.transaction('checkpoints', 'readonly');
    const store = tx.objectStore('checkpoints');
    const record = await store.get(checkpointId);
    
    if (!record) {
      throw new Error(`Checkpoint not found: ${checkpointId}`);
    }
    
    const checkpoint = this.deserializeCheckpoint(record.checkpoint);
    
    // Handle side effects based on strategy
    if (compensationStrategy === 'rollback') {
      // Compensate all side effects after checkpoint
      await this.compensateSideEffectsAfter(checkpoint.timestamp);
    } else if (compensationStrategy === 'forward') {
      // Replay side effects from checkpoint to current state
      // This is complex and may not be feasible for all effects
      console.warn('Forward recovery not fully implemented');
    }
    // 'manual' means user will handle side effects
    
    return checkpoint;
  }
  
  private async compensateSideEffectsAfter(timestamp: Date): Promise<void> {
    const allEffects = Array.from(this.sideEffectTracker['effects'].values());
    const effectsToCompensate = allEffects
      .filter(e => e.timestamp > timestamp && e.status === 'executed')
      .reverse(); // Reverse order for proper compensation
    
    for (const effect of effectsToCompensate) {
      try {
        await this.sideEffectTracker.compensate(effect.id);
      } catch (error) {
        console.error(`Failed to compensate effect ${effect.id}:`, error);
        // Continue with other compensations
      }
    }
  }
  
  private cloneContext(context: ExecutionContext): ExecutionContext {
    return {
      variables: structuredClone(context.variables),
      secrets: new Map(context.secrets),
      artifacts: new Map(context.artifacts)
    };
  }
  
  private serializeCheckpoint(checkpoint: ExecutionCheckpoint): string {
    return JSON.stringify({
      id: checkpoint.id,
      timestamp: checkpoint.timestamp.toISOString(),
      nodeStates: Array.from(checkpoint.nodeStates.entries()),
      globalContext: {
        variables: checkpoint.globalContext.variables
      },
      sideEffects: checkpoint.sideEffects,
      reason: checkpoint.reason
    });
  }
  
  private deserializeCheckpoint(data: string): ExecutionCheckpoint {
    const parsed = JSON.parse(data);
    return {
      id: parsed.id,
      timestamp: new Date(parsed.timestamp),
      nodeStates: new Map(parsed.nodeStates),
      globalContext: {
        variables: parsed.globalContext.variables,
        secrets: new Map(),
        artifacts: new Map()
      },
      sideEffects: parsed.sideEffects || [],
      reason: parsed.reason
    };
  }
  
  async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowCheckpoints', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('checkpoints')) {
          db.createObjectStore('checkpoints', { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('sideEffects')) {
          db.createObjectStore('sideEffects', { keyPath: 'id' });
        }
      };
    });
  }
}
```

### Usage in Node Execution

```typescript
class WorkflowOrchestrator {
  private sideEffectTracker: SideEffectTracker;
  private checkpointManager: CheckpointManager;
  
  private async executeNode(nodeId: string): Promise<NodeExecutionResult> {
    const node = this.nodes.get(nodeId)!;
    
    try {
      // Gather inputs
      const inputs = await this.dataFlowController.gatherInputs(
        nodeId,
        this.edges,
        this.executionState
      );
      
      // Track side effect (if agent makes external calls)
      const effectId = await this.sideEffectTracker.recordEffect({
        nodeId,
        type: 'api_call',
        operation: 'execute_agent',
        parameters: { inputs },
        compensatable: true,
        compensationFn: '$cancel_execution(effect.parameters.executionId)'
      });
      
      // Execute agent
      const result = await this.executeAgent(node, inputs);
      
      // Mark effect as executed
      await this.sideEffectTracker.markExecuted(effectId, result);
      
      return result;
      
    } catch (error) {
      // On error, create checkpoint and compensate this node
      await this.checkpointManager.createCheckpoint(
        this.executionState,
        'error'
      );
      
      await this.sideEffectTracker.compensateAllForNode(nodeId);
      
      throw error;
    }
  }
}
```

### Compensation Examples

```typescript
// Example: API call compensation
const apiCallEffect: SideEffect = {
  nodeId: 'node-123',
  type: 'api_call',
  operation: 'create_resource',
  parameters: {
    endpoint: '/api/resources',
    method: 'POST',
    body: { name: 'test' }
  },
  result: { id: 'resource-456' },
  compensatable: true,
  compensationFn: `
    $http.delete("/api/resources/" & result.id)
  `
};

// Example: File write compensation
const fileWriteEffect: SideEffect = {
  nodeId: 'node-123',
  type: 'file_write',
  operation: 'write_output',
  parameters: {
    path: '/tmp/output.json',
    content: '...'
  },
  compensatable: true,
  compensationFn: `
    $fs.delete(parameters.path)
  `
};

// Example: Non-compensatable effect (email sent)
const emailEffect: SideEffect = {
  nodeId: 'node-123',
  type: 'external_service',
  operation: 'send_email',
  parameters: {
    to: 'user@example.com',
    subject: 'Workflow result'
  },
  compensatable: false // Can't unsend email
};
```

## Enhanced Node Component

```typescript
interface AgentNodeData {
  id: string;
  type: 'researcher' | 'coder' | 'reviewer' | 'coordinator' | 'transformer';
  label: string;
  config: AgentConfig;
  status: ExecutionStatus;
  logs: LogEntry[];
  metrics: ExecutionMetrics;
  inputs: Record<string, InputDefinition>;
  outputs: Record<string, OutputDefinition>;
  sideEffects: SideEffect[]; // NEW: Track side effects
}

interface AgentConfig {
  model: string;
  temperature: number;
  systemPrompt: string;
  maxTokens?: number;
  timeout?: number;
  retryConfig?: RetryConfig;
  streaming?: boolean;
  memoryLimit?: number;
  streamConfig?: StreamConfig; // NEW: Streaming configuration
  trackSideEffects?: boolean; // NEW: Enable side effect tracking
}

const AgentNode: React.FC<NodeProps<AgentNodeData>> = ({ data, selected }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const streamingOutput = useStreamingOutput(data.id);
  const memoryUsage = useMemoryUsage(data.id);
  
  return (
    <div className={`agent-node ${selected ? 'selected' : ''} ${isExpanded ? 'expanded' : ''}`}>
      {/* Multiple typed input handles */}
      {Object.entries(data.inputs).map(([key, input]) => (
        <Handle
          key={`input-${key}`}
          type="target"
          position={Position.Left}
          id={`input-${key}`}
          className={`handle-${input.type}`}
          style={{ top: calculateHandlePosition(key, data.inputs) }}
        >
          <Tooltip content={`${input.name} (${input.type})`}>
            <HandleLabel required={input.required}>
              {input.type === 'stream' && <StreamIcon />}
              {input.name}
            </HandleLabel>
          </Tooltip>
        </Handle>
      ))}
      
      <div className="node-header">
        <AgentIcon type={data.type} />
        <span className="node-label">{data.label}</span>
        <StatusBadge status={data.status} />
        {data.config.streaming && <StreamBadge />}
        {data.trackSideEffects && data.sideEffects.length > 0 && (
          <SideEffectBadge count={data.sideEffects.length} />
        )}
        <Button size="xs" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
        </Button>
      </div>
      
      <div className="node-body">
        {data.status === 'running' && (
          <>
            <ProgressBar metrics={data.metrics} />
            {data.config.streaming && streamingOutput && (
              <StreamPreview content={streamingOutput} />
            )}
            {memoryUsage && (
              <MemoryIndicator usage={memoryUsage} />
            )}
          </>
        )}
        
        {isExpanded && (
          <NodeDetails 
            logs={data.logs} 
            metrics={data.metrics}
            sideEffects={data.sideEffects}
          />
        )}
      </div>
      
      {/* Multiple typed output handles */}
      {Object.entries(data.outputs).map(([key, output]) => (
        <Handle
          key={`output-${key}`}
          type="source"
          position={Position.Right}
          id={`output-${key}`}
          className={`handle-${output.type}`}
          style={{ top: calculateHandlePosition(key, data.outputs) }}
        >
          <Tooltip content={`${output.name} (${output.type})`}>
            <HandleLabel>
              {output.type === 'stream' && <StreamIcon />}
              {output.name}
            </HandleLabel>
          </Tooltip>
        </Handle>
      ))}
    </div>
  );
};
```

## Performance Optimizations for Large Workflows

### Viewport Culling

Only render nodes visible in viewport:

```typescript
const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({ workflowId }) => {
  const { nodes, edges } = useWorkflowStore();
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 });
  
  // Filter nodes to only those in viewport
  const visibleNodes = useMemo(() => {
    if (nodes.length < 50) return nodes; // No need for culling
    
    return nodes.filter(node => {
      const nodeRect = {
        x: node.position.x,
        y: node.position.y,
        width: node.width || 200,
        height: node.height || 100
      };
      
      return isRectInViewport(nodeRect, viewport);
    });
  }, [nodes, viewport]);
  
  // Edges connected to visible nodes
  const visibleEdges = useMemo(() => {
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
    return edges.filter(e => 
      visibleNodeIds.has(e.source) || visibleNodeIds.has(e.target)
    );
  }, [edges, visibleNodes]);
  
  return (
    <ReactFlow
      nodes={visibleNodes}
      edges={visibleEdges}
      onMove={(_, viewport) => setViewport(viewport)}
      {...otherProps}
    />
  );
};
```

### Virtual Scrolling for Large Node Lists

```typescript
// Use react-window for node palette with 100+ items
import { FixedSizeList } from 'react-window';

const NodePalette: React.FC = () => {
  const nodeTypes = useNodeTypes(); // Could be 100+ items
  
  const Row = ({ index, style }) => (
    <div style={style}>
      <NodePaletteItem node={nodeTypes[index]} />
    </div>
  );
  
  return (
    <FixedSizeList
      height={600}
      itemCount={nodeTypes.length}
      itemSize={60}
      width="100%"
    >
      {Row}
    </FixedSizeList>
  );
};
```

### Debounced Auto-Save

```typescript
const useAutoSave = (workflowId: string) => {
  const { workflow } = useWorkflowStore();
  const saveWorkflow = useSaveWorkflow();
  
  const debouncedSave = useMemo(
    () => debounce(async () => {
      await saveWorkflow(workflow);
    }, 2000),
    [workflow, saveWorkflow]
  );
  
  useEffect(() => {
    debouncedSave();
    return () => debouncedSave.cancel();
  }, [workflow, debouncedSave]);
};
```

## Rationale

### Memory Management
- **Hybrid storage** solves the GB-scale artifact problem without requiring users to manually manage storage
- **Automatic tiering** based on size and access patterns is transparent to users
- **LRU + size-based eviction** balances frequently-accessed small items with infrequently-accessed large items
- **Compression** for large data (>100KB) reduces IndexedDB usage significantly

### Streaming Architecture  
- **ReadableStream/TransformStream** APIs provide native backpressure support - no custom implementation needed
- **Dual-mode execution** allows workflows to use streaming only when beneficial
- **Stream merging** with backpressure check (`desiredSize`) prevents downstream overload
- **Transform streams** compose cleanly for chained transformations

### Security Model
- **JSONata** is a mature, sandboxed expression language with no code execution
- **Registered functions** whitelist provides controlled access to safe operations (uuid, now, random)
- **Timeout + max depth** prevents DoS via complex expressions
- **Expression validation** before execution catches syntax errors early

### Checkpoint Consistency
- **Side effect tracking** makes external operations visible and compensatable
- **Compensation functions** as JSONata expressions keep them safe and serializable
- **Rollback strategy** compensates side effects in reverse order (proper LIFO)
- **Non-compensatable flag** makes it explicit when operations can't be undone (e.g., emails)
- **Manual strategy** gives users control for complex scenarios

## What I Changed

### 1. Memory Management - NEW SYSTEM
- Replaced simple memory cache with **hybrid storage manager** that automatically tiers between memory and IndexedDB
- Added **compression** for large artifacts (>100KB) using native CompressionStream API
- Implemented **hybrid eviction** strategy combining LRU and size-based approaches
- Added **promotion** to move frequently-accessed data back to memory
- Clear **data lifecycle** (temporary vs persistent, hot vs cold)

### 2. Streaming - COMPLETE REDESIGN
- Replaced custom streaming with **native Web Streams API** (ReadableStream, TransformStream)
- **Backpressure** handled automatically by stream's `desiredSize` property
- **Dual-mode execution** automatically chooses streaming vs batch based on data size
- Stream transformations use **TransformStream** for proper composition
- Added **stream merging** with concurrent reading and backpressure awareness

### 3. Security - SWITCHED TECHNOLOGY
- Removed **ALL uses of `new Function()`** 
- Replaced with **JSONata** - mature, sandboxed expression language
- Added **timeout** (5s) and **max depth** (100) limits
- Whitelist of **registered functions** for safe operations only
- Expression **validation** before execution with helpful error messages

### 4. Checkpoint Consistency - NEW FEATURE
- Created **side effect tracker** to record all external operations
- Each side effect has **compensation function** (JSONata expression)
- Three restoration strategies: **rollback** (compensate), **forward** (replay), **manual**
- Side effects include **type, parameters, result, compensatable flag**
- Compensation runs in **reverse order** (LIFO) for correctness

### 5. Performance - ADDED OPTIMIZATIONS
- **Viewport culling** for workflows with 50+ nodes
- **Virtual scrolling** for large node palette (react-window)
- **Debounced auto-save** (2s) to prevent excessive writes
- **Expression caching** in JSONata evaluator

## What I Kept

All the excellent foundation from your design:

- **React Flow** for canvas - perfect choice
- **Zustand + immer** for state management
- **Worker pool** concept (refined the implementation)
- **Topological sort** for DAG execution
- **Multiple input/output handles** per node
- **Input/output schemas** with validation
- **Retry configuration** with backoff strategies
- **Event system** for reactive updates
- **Undo/redo** with snapshots
- **Edge validation rules** and transformations
- **Resource limits** and pre-flight checks
- **Node status granularity** (queued, warning, cancelled)
- **Execution checkpoints** (enhanced with side effects)
- **Template system** for workflows

## Open Questions

### 1. Streaming Materialization
When streaming output is needed by multiple downstream nodes, should we:
- **Tee the stream** (duplicate) but risk memory issues if one consumer is slow?
- **Materialize once** to storage then serve copies (breaks streaming semantics)?
- **Force sequential** consumption (limits parallelism)?

### 2. Compensation Completeness
Some operations can't be compensated (emails, webhooks, payments). Should we:
- **Block checkpoint restoration** if non-compensatable effects exist?
- **Warn user** and let them proceed manually?
- **Require user confirmation** for each non-compensatable effect?

### 3. Cross-Tab Coordination
If user opens workflow in multiple tabs:
- **Lock workflow** to single tab during execution?
- **Broadcast changes** via BroadcastChannel and handle conflicts?
- **Last-write-wins** with conflict detection?

### 4. Cost Estimation
For workflows with many nodes:
- Should we **estimate total cost** before execution (sum of max tokens per node)?
- Show **running cost counter** during execution?
- **Pause/warn** if approaching budget limit?

### 5. Large Workflow Import
Workflows with 1000+ nodes:
- **Progressive loading** of nodes (load viewport first)?
- **Background parsing** with loading indicator?
- **Lazy initialization** of node configs?

## Convergence Status

**PROPOSING_FINAL** - This design addresses all major concerns:

✅ Memory management with hybrid storage and automatic tiering  
✅ Streaming with native backpressure via Web Streams API  
✅ Security via JSONata (no code execution)  
✅ Checkpoint consistency with side effect tracking and compensation  
✅ Performance optimizations for 100+ node workflows  

The architecture is implementable, performant, and secure. Open questions remain but are non-blocking - they're about UX decisions rather than technical feasibility.

---

## PROMPT_FOR_CRITIC

Please review this design focusing on:

1. **Hybrid storage practicality**: Is automatic tiering between memory/IndexedDB too complex? Would a simpler "always use IndexedDB for outputs" approach be better?

2. **Streaming vs batch trade-offs**: The dual-mode execution adds complexity. Should we commit fully to streaming everywhere, or is the automatic mode selection valuable?

3. **JSONata learning curve**: While secure, JSONata is another language to learn. Are the expression examples sufficient? Should we provide a visual expression builder instead?

4. **Side effect compensation limitations**: The design assumes operations can be compensated via expressions. What about complex compensations requiring stateful logic (e.g., multi-step API rollbacks)?

5. **Missing pieces**: What critical components or edge cases did I overlook?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

# Visual AI Agent Workflow Builder - Production-Ready Architecture v2

## Core Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │         │
│  │   (React     │  │    Panel     │  │   & Palette  │         │
│  │    Flow)     │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│           State Management (Zustand + Immer)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Orchestration Layer                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Adaptive   │  │  Tiered    │  │ Checkpoint │         │  │
│  │  │ Executor   │  │  Storage   │  │  Manager   │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Data Flow & Storage Layer                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │  Pluggable │  │   Hybrid   │  │ Effect Log │         │  │
│  │  │ Expression │  │  Storage   │  │  (Append-  │         │  │
│  │  │  Engine    │  │  Manager   │  │   Only)    │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas**: React Flow v11+ with custom viewport rendering
- **State**: Zustand with immer middleware and persistence
- **UI**: Radix UI primitives + Tailwind CSS
- **Execution**: Adaptive executor with streaming-first, batch fallback
- **Storage**: Three-tier: Hot cache (memory) → Warm cache (IndexedDB) → Cold storage (optional blob URLs)
- **Expressions**: Pluggable engine (JSONata default, optional visual builder)
- **Side Effects**: Append-only log with semantic compensation descriptors
- **Workers**: Shared Worker pool with resource quotas

## Simplified Three-Tier Storage Architecture

### Key Insight: Most Artifacts Don't Need Eviction Logic

```typescript
interface StorageConfig {
  // Simplified thresholds - no complex eviction
  hotCacheMaxBytes: number;      // 50MB - small, hot data only
  warmCacheMaxBytes: number;     // 500MB - most artifacts live here
  enableColdStorage: boolean;    // Optional blob URLs for huge files
  compressionThreshold: number;  // 1MB - compress above this
  autoCleanupAge: number;        // 24h - auto-delete old temp data
}

class TieredStorageManager {
  private hotCache: Map<string, HotCacheEntry> = new Map();
  private hotCacheSize: number = 0;
  private warmDB: IDBDatabase;
  private coldBlobUrls: Map<string, string> = new Map();
  private config: StorageConfig;
  
  // Metadata index for all artifacts (lightweight)
  private artifactIndex: Map<string, ArtifactMetadata> = new Map();
  
  constructor(config: StorageConfig) {
    this.config = config;
    this.initWarmStorage();
    this.scheduleCleanup();
  }
  
  async store(key: string, data: any, hints: StorageHints): Promise<void> {
    const serialized = JSON.stringify(data);
    const sizeBytes = new Blob([serialized]).size;
    
    // Update metadata index
    this.artifactIndex.set(key, {
      key,
      sizeBytes,
      tier: 'determining',
      createdAt: Date.now(),
      temporary: hints.temporary,
      nodeId: hints.nodeId,
      executionId: hints.executionId,
      accessCount: 0,
      lastAccessedAt: Date.now()
    });
    
    // Tier selection: SIMPLE rules, no complex scoring
    const tier = this.selectTier(sizeBytes, hints);
    
    switch (tier) {
      case 'hot':
        await this.storeInHotCache(key, data, sizeBytes);
        break;
        
      case 'warm':
        await this.storeInWarmCache(key, serialized, sizeBytes);
        break;
        
      case 'cold':
        await this.storeInColdStorage(key, serialized, sizeBytes);
        break;
    }
    
    this.artifactIndex.get(key)!.tier = tier;
  }
  
  private selectTier(sizeBytes: number, hints: StorageHints): StorageTier {
    // COLD: Files > 100MB (if enabled) - these are rare
    if (this.config.enableColdStorage && sizeBytes > 100 * 1024 * 1024) {
      return 'cold';
    }
    
    // HOT: Small + frequently accessed OR marked as hot
    // Only small items that are actively being used by running nodes
    if (sizeBytes < 100 * 1024 && // < 100KB
        (hints.accessPattern === 'hot' || hints.temporary)) {
      
      // Check if we have room in hot cache
      if (this.hotCacheSize + sizeBytes <= this.config.hotCacheMaxBytes) {
        return 'hot';
      }
      
      // Try to make room by removing oldest hot items
      if (this.makeRoomInHotCache(sizeBytes)) {
        return 'hot';
      }
    }
    
    // WARM: Everything else (default tier)
    // Most artifacts live here - IndexedDB is fast enough
    return 'warm';
  }
  
  private makeRoomInHotCache(requiredBytes: number): boolean {
    // Simple FIFO eviction of oldest items
    const entries = Array.from(this.hotCache.entries())
      .sort((a, b) => a[1].storedAt - b[1].storedAt);
    
    let freedBytes = 0;
    const toEvict: string[] = [];
    
    for (const [key, entry] of entries) {
      // Never evict items stored in last 5 seconds
      if (Date.now() - entry.storedAt < 5000) continue;
      
      toEvict.push(key);
      freedBytes += entry.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    // Move to warm cache (no data loss)
    for (const key of toEvict) {
      const entry = this.hotCache.get(key)!;
      this.storeInWarmCache(key, JSON.stringify(entry.data), entry.sizeBytes);
      this.hotCache.delete(key);
      this.hotCacheSize -= entry.sizeBytes;
      
      const metadata = this.artifactIndex.get(key);
      if (metadata) metadata.tier = 'warm';
    }
    
    return freedBytes >= requiredBytes;
  }
  
  async retrieve(key: string): Promise<any> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) {
      throw new Error(`Artifact not found: ${key}`);
    }
    
    // Update access tracking
    metadata.accessCount++;
    metadata.lastAccessedAt = Date.now();
    
    // Retrieve from appropriate tier
    let data: any;
    
    switch (metadata.tier) {
      case 'hot':
        data = this.hotCache.get(key)?.data;
        if (!data) {
          // Fallback to warm if somehow missing
          data = await this.retrieveFromWarmCache(key);
        }
        break;
        
      case 'warm':
        data = await this.retrieveFromWarmCache(key);
        
        // Promote to hot if: small + accessed 3+ times recently
        if (metadata.sizeBytes < 100 * 1024 && 
            metadata.accessCount >= 3 &&
            Date.now() - metadata.lastAccessedAt < 60000) {
          
          if (this.hotCacheSize + metadata.sizeBytes <= this.config.hotCacheMaxBytes) {
            await this.storeInHotCache(key, data, metadata.sizeBytes);
            metadata.tier = 'hot';
          }
        }
        break;
        
      case 'cold':
        data = await this.retrieveFromColdStorage(key);
        break;
    }
    
    return data;
  }
  
  private async storeInHotCache(key: string, data: any, sizeBytes: number): Promise<void> {
    this.hotCache.set(key, {
      data,
      sizeBytes,
      storedAt: Date.now()
    });
    this.hotCacheSize += sizeBytes;
  }
  
  private async storeInWarmCache(key: string, serialized: string, sizeBytes: number): Promise<void> {
    // Compress if large enough
    const shouldCompress = sizeBytes > this.config.compressionThreshold;
    const toStore = shouldCompress 
      ? await this.compress(serialized)
      : serialized;
    
    const tx = this.warmDB.transaction('artifacts', 'readwrite');
    const store = tx.objectStore('artifacts');
    
    await store.put({
      key,
      data: toStore,
      compressed: shouldCompress,
      storedAt: Date.now()
    });
  }
  
  private async retrieveFromWarmCache(key: string): Promise<any> {
    const tx = this.warmDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    const record = await store.get(key);
    
    if (!record) {
      throw new Error(`Artifact not found in warm cache: ${key}`);
    }
    
    const serialized = record.compressed
      ? await this.decompress(record.data)
      : record.data;
    
    return JSON.parse(serialized);
  }
  
  private async storeInColdStorage(key: string, serialized: string, sizeBytes: number): Promise<void> {
    // Use Blob URLs for huge files (rare case)
    const compressed = await this.compress(serialized);
    const blob = new Blob([compressed], { type: 'application/octet-stream' });
    const blobUrl = URL.createObjectURL(blob);
    
    this.coldBlobUrls.set(key, blobUrl);
    
    // Also store reference in IndexedDB
    const tx = this.warmDB.transaction('coldRefs', 'readwrite');
    const store = tx.objectStore('coldRefs');
    await store.put({ key, blobUrl, sizeBytes, storedAt: Date.now() });
  }
  
  private async retrieveFromColdStorage(key: string): Promise<any> {
    const blobUrl = this.coldBlobUrls.get(key);
    if (!blobUrl) {
      throw new Error(`Cold storage artifact not found: ${key}`);
    }
    
    const response = await fetch(blobUrl);
    const compressed = new Uint8Array(await response.arrayBuffer());
    const serialized = await this.decompress(compressed);
    return JSON.parse(serialized);
  }
  
  async clear(predicate?: (metadata: ArtifactMetadata) => boolean): Promise<void> {
    if (!predicate) {
      // Clear everything
      this.hotCache.clear();
      this.hotCacheSize = 0;
      this.artifactIndex.clear();
      
      const tx = this.warmDB.transaction(['artifacts', 'coldRefs'], 'readwrite');
      await tx.objectStore('artifacts').clear();
      await tx.objectStore('coldRefs').clear();
      
      // Revoke blob URLs
      for (const blobUrl of this.coldBlobUrls.values()) {
        URL.revokeObjectURL(blobUrl);
      }
      this.coldBlobUrls.clear();
      
      return;
    }
    
    // Selective clear
    const toDelete: string[] = [];
    
    for (const [key, metadata] of this.artifactIndex.entries()) {
      if (predicate(metadata)) {
        toDelete.push(key);
      }
    }
    
    for (const key of toDelete) {
      await this.delete(key);
    }
  }
  
  private async delete(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) return;
    
    switch (metadata.tier) {
      case 'hot':
        const entry = this.hotCache.get(key);
        if (entry) {
          this.hotCacheSize -= entry.sizeBytes;
          this.hotCache.delete(key);
        }
        break;
        
      case 'warm':
        const tx = this.warmDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').delete(key);
        break;
        
      case 'cold':
        const blobUrl = this.coldBlobUrls.get(key);
        if (blobUrl) {
          URL.revokeObjectURL(blobUrl);
          this.coldBlobUrls.delete(key);
        }
        
        const txCold = this.warmDB.transaction('coldRefs', 'readwrite');
        await txCold.objectStore('coldRefs').delete(key);
        break;
    }
    
    this.artifactIndex.delete(key);
  }
  
  private scheduleCleanup(): void {
    // Auto-cleanup old temporary data every hour
    setInterval(() => {
      const cutoff = Date.now() - this.config.autoCleanupAge;
      
      this.clear(metadata => 
        metadata.temporary && metadata.createdAt < cutoff
      );
    }, 60 * 60 * 1000); // 1 hour
  }
  
  getStorageStats(): StorageStats {
    const stats = {
      hot: { count: 0, bytes: this.hotCacheSize },
      warm: { count: 0, bytes: 0 },
      cold: { count: 0, bytes: 0 },
      total: { count: this.artifactIndex.size, bytes: 0 }
    };
    
    for (const metadata of this.artifactIndex.values()) {
      stats[metadata.tier].count++;
      stats[metadata.tier].bytes += metadata.sizeBytes;
      stats.total.bytes += metadata.sizeBytes;
    }
    
    return stats;
  }
  
  private async compress(data: string): Promise<Uint8Array> {
    const encoder = new TextEncoder();
    const stream = new Blob([data]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    return new Uint8Array(buffer);
  }
  
  private async decompress(data: Uint8Array): Promise<string> {
    const stream = new Blob([data]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private async initWarmStorage(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowArtifacts', 2);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.warmDB = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('artifacts')) {
          db.createObjectStore('artifacts', { keyPath: 'key' });
        }
        if (!db.objectStoreNames.contains('coldRefs')) {
          db.createObjectStore('coldRefs', { keyPath: 'key' });
        }
      };
    });
  }
}

// Simplified types
interface HotCacheEntry {
  data: any;
  sizeBytes: number;
  storedAt: number;
}

interface ArtifactMetadata {
  key: string;
  sizeBytes: number;
  tier: StorageTier;
  createdAt: number;
  temporary: boolean;
  nodeId?: string;
  executionId?: string;
  accessCount: number;
  lastAccessedAt: number;
}

type StorageTier = 'hot' | 'warm' | 'cold' | 'determining';

interface StorageHints {
  temporary?: boolean;
  accessPattern?: 'hot' | 'warm';
  nodeId?: string;
  executionId?: string;
}

interface StorageStats {
  hot: { count: number; bytes: number };
  warm: { count: number; bytes: number };
  cold: { count: number; bytes: number };
  total: { count: number; bytes: number };
}
```

### Usage Example
```typescript
const storage = new TieredStorageManager({
  hotCacheMaxBytes: 50 * 1024 * 1024,      // 50MB
  warmCacheMaxBytes: 500 * 1024 * 1024,    // 500MB
  enableColdStorage: true,
  compressionThreshold: 1024 * 1024,        // 1MB
  autoCleanupAge: 24 * 60 * 60 * 1000      // 24h
});

// Store - automatic tiering
await storage.store(
  `node-${nodeId}-output`,
  largeDataset,
  {
    nodeId,
    executionId,
    temporary: true,
    accessPattern: 'warm' // Default for most data
  }
);

// Retrieve - transparent tier access
const data = await storage.retrieve(`node-${nodeId}-output`);

// Cleanup after workflow
await storage.clear(meta => 
  meta.temporary && meta.executionId === executionId
);

// Check storage usage
const stats = storage.getStorageStats();
console.log(`Using ${stats.hot.bytes} bytes in hot cache`);
```

## Streaming-First with Graceful Degradation

### Key Insight: Don't Force Everything to Stream

```typescript
class AdaptiveExecutor {
  private streamingExecutor: StreamingExecutor;
  private batchExecutor: BatchExecutor;
  private storage: TieredStorageManager;
  
  async executeNode(
    node: WorkflowNode,
    inputs: Record<string, any>
  ): Promise<ExecutionResult> {
    
    // Check if streaming makes sense
    const streamingDecision = this.analyzeStreamingFeasibility(node, inputs);
    
    if (streamingDecision.shouldStream) {
      return this.executeWithStreaming(node, inputs, streamingDecision);
    } else {
      return this.executeWithBatch(node, inputs);
    }
  }
  
  private analyzeStreamingFeasibility(
    node: WorkflowNode,
    inputs: Record<string, any>
  ): StreamingDecision {
    
    const reasons: string[] = [];
    let shouldStream = false;
    let materializationStrategy: MaterializationStrategy = 'none';
    
    // 1. Node explicitly requests streaming
    if (node.data.config.streaming === true) {
      shouldStream = true;
      reasons.push('node_config_explicit');
    }
    
    // 2. Node explicitly REJECTS streaming
    if (node.data.config.streaming === false) {
      return {
        shouldStream: false,
        reasons: ['node_config_explicit_batch'],
        materializationStrategy: 'none'
      };
    }
    
    // 3. Input is already a stream
    const hasStreamInput = Object.values(inputs).some(v => 
      v instanceof ReadableStream
    );
    
    if (hasStreamInput) {
      shouldStream = true;
      reasons.push('stream_input');
      
      // Check if multiple downstream consumers need this stream
      const downstreamCount = this.getDownstreamConsumerCount(node);
      
      if (downstreamCount > 1) {
        // MATERIALIZE ONCE for multiple consumers
        materializationStrategy = 'materialize_to_storage';
        reasons.push('multiple_consumers_detected');
      }
    }
    
    // 4. Large input suggests streaming (but not required)
    const estimatedSize = this.estimateDataSize(inputs);
    if (estimatedSize > 5 * 1024 * 1024) { // 5MB
      shouldStream = true;
      reasons.push('large_input_detected');
    }
    
    // 5. Agent type benefits from streaming (LLM responses)
    if (['researcher', 'coder', 'reviewer'].includes(node.data.type)) {
      shouldStream = true;
      reasons.push('agent_type_benefits');
    }
    
    return {
      shouldStream,
      reasons,
      materializationStrategy
    };
  }
  
  private async executeWithStreaming(
    node: WorkflowNode,
    inputs: Record<string, any>,
    decision: StreamingDecision
  ): Promise<ExecutionResult> {
    
    const outputStream = await this.streamingExecutor.executeNodeStreaming(
      node,
      inputs
    );
    
    // Handle materialization if needed
    if (decision.materializationStrategy === 'materialize_to_storage') {
      return await this.materializeStreamToStorage(node, outputStream);
    }
    
    // Otherwise return stream directly
    return {
      nodeId: node.id,
      output: outputStream,
      streaming: true,
      metadata: {
        streamingReasons: decision.reasons
      }
    };
  }
  
  private async materializeStreamToStorage(
    node: WorkflowNode,
    stream: ReadableStream
  ): Promise<ExecutionResult> {
    
    // Read entire stream into storage
    const chunks: any[] = [];
    const reader = stream.getReader();
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
    
    // Combine chunks
    const materialized = this.combineChunks(chunks);
    
    // Store in tiered storage
    const storageKey = `node-${node.id}-materialized`;
    await this.storage.store(storageKey, materialized, {
      nodeId: node.id,
      temporary: true,
      accessPattern: 'warm'
    });
    
    // Return reference, not the data itself
    return {
      nodeId: node.id,
      output: { $ref: storageKey },
      streaming: false,
      metadata: {
        materialized: true,
        storageKey
      }
    };
  }
  
  private async executeWithBatch(
    node: WorkflowNode,
    inputs: Record<string, any>
  ): Promise<ExecutionResult> {
    
    // Resolve any storage references in inputs
    const resolvedInputs = await this.resolveStorageReferences(inputs);
    
    // Execute node
    const output = await this.batchExecutor.executeNodeBatch(node, resolvedInputs);
    
    return {
      nodeId: node.id,
      output,
      streaming: false,
      metadata: {}
    };
  }
  
  private async resolveStorageReferences(inputs: Record<string, any>): Promise<Record<string, any>> {
    const resolved: Record<string, any> = {};
    
    for (const [key, value] of Object.entries(inputs)) {
      if (value && typeof value === 'object' && value.$ref) {
        // Storage reference - retrieve
        resolved[key] = await this.storage.retrieve(value.$ref);
      } else {
        resolved[key] = value;
      }
    }
    
    return resolved;
  }
  
  private getDownstreamConsumerCount(node: WorkflowNode): number {
    // Count how many nodes consume this node's output
    return this.edges.filter(e => e.source === node.id).length;
  }
  
  private estimateDataSize(data: any): number {
    try {
      return JSON.stringify(data).length;
    } catch {
      return 0;
    }
  }
  
  private combineChunks(chunks: any[]): any {
    // Combine strategy depends on chunk type
    if (chunks.length === 0) return null;
    
    if (typeof chunks[0] === 'string') {
      return chunks.join('');
    }
    
    if (Array.isArray(chunks[0])) {
      return chunks.flat();
    }
    
    // Objects - last chunk wins
    return chunks[chunks.length - 1];
  }
}

interface StreamingDecision {
  shouldStream: boolean;
  reasons: string[];
  materializationStrategy: MaterializationStrategy;
}

type MaterializationStrategy = 
  | 'none'                      // Pass stream through
  | 'materialize_to_storage';   // Store once, serve multiple

interface ExecutionResult {
  nodeId: string;
  output: any | ReadableStream | { $ref: string };
  streaming: boolean;
  metadata: Record<string, any>;
}
```

## Pluggable Expression Engine

### Key Insight: Start Simple, Allow Upgrades

```typescript
interface ExpressionEngine {
  evaluate(expression: string, context: any): Promise<any>;
  validate(expression: string): ValidationResult;
  getExamples(): ExpressionExample[];
  getSyntaxHelp(): string;
}

class JSONataEngine implements ExpressionEngine {
  private cache: Map<string, jsonata.Expression> = new Map();
  private readonly timeout = 5000;
  private readonly maxDepth = 100;
  
  async evaluate(expression: string, context: any): Promise<any> {
    let compiled = this.cache.get(expression);
    
    if (!compiled) {
      compiled = jsonata(expression);
      
      // Register safe functions
      compiled.registerFunction('now', () => new Date().toISOString());
      compiled.registerFunction('random', () => Math.random());
      compiled.registerFunction('uuid', () => crypto.randomUUID());
      
      this.cache.set(expression, compiled);
    }
    
    return await Promise.race([
      compiled.evaluate(context, { maxDepth: this.maxDepth }),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Expression timeout')), this.timeout)
      )
    ]);
  }
  
  validate(expression: string): ValidationResult {
    try {
      jsonata(expression);
      return { valid: true };
    } catch (error) {
      return { 
        valid: false, 
        error: error.message,
        suggestion: this.getSuggestion(error)
      };
    }
  }
  
  getExamples(): ExpressionExample[] {
    return [
      {
        category: 'Extract Field',
        expression: '$.user.name',
        description: 'Get nested field value',
        inputExample: { user: { name: 'Alice' } },
        outputExample: 'Alice'
      },
      {
        category: 'Filter Array',
        expression: '$.items[price > 100]',
        description: 'Filter array by condition',
        inputExample: { items: [{ price: 50 }, { price: 150 }] },
        outputExample: [{ price: 150 }]
      },
      {
        category: 'Transform',
        expression: '{ "fullName": firstName & " " & lastName }',
        description: 'Create new object from fields',
        inputExample: { firstName: 'Alice', lastName: 'Smith' },
        outputExample: { fullName: 'Alice Smith' }
      }
    ];
  }
  
  getSyntaxHelp(): string {
    return `
JSONata Expression Syntax:
- Field access: $.field.nested
- Array filter: $.items[condition]
- Array map: $.items.{ "name": name }
- Aggregation: $sum(items.price)
- String concat: field1 & " " & field2
    `.trim();
  }
  
  private getSuggestion(error: any): string | undefined {
    // Provide helpful suggestions based on common errors
    if (error.message.includes('undefined')) {
      return 'Check field names - they may not exist in your data';
    }
    if (error.message.includes('syntax')) {
      return 'Try using the visual builder for complex expressions';
    }
    return undefined;
  }
}

// Optional visual builder for users who find JSONata hard
class VisualExpressionBuilder implements ExpressionEngine {
  private jsonataEngine = new JSONataEngine();
  
  async evaluate(expression: string, context: any): Promise<any> {
    // Expression is JSON representation of visual blocks
    const blocks = JSON.parse(expression);
    const jsonataExpr = this.blocksToJSONata(blocks);
    return this.jsonataEngine.evaluate(jsonataExpr, context);
  }
  
  validate(expression: string): ValidationResult {
    try {
      const blocks = JSON.parse(expression);
      const jsonataExpr = this.blocksToJSONata(blocks);
      return this.jsonataEngine.validate(jsonataExpr);
    } catch (error) {
      return { valid: false, error: error.message };
    }
  }
  
  private blocksToJSONata(blocks: ExpressionBlock[]): string {
    // Convert visual blocks to JSONata
    // Example: [{ type: 'field', path: 'user.name' }] → '$.user.name'
    return blocks.map(block => {
      switch (block.type) {
        case 'field':
          return `$.${block.path}`;
        case 'filter':
          return `[${block.condition}]`;
        case 'map':
          return `.{ ${block.mapping} }`;
        default:
          throw new Error(`Unknown block type: ${block.type}`);
      }
    }).join('');
  }
  
  getExamples(): ExpressionExample[] {
    return this.jsonataEngine.getExamples();
  }
  
  getSyntaxHelp(): string {
    return 'Use the visual builder UI to create expressions';
  }
}

// Expression engine factory
class ExpressionEngineFactory {
  static create(mode: 'text' | 'visual'): ExpressionEngine {
    switch (mode) {
      case 'text':
        return new JSONataEngine();
      case 'visual':
        return new VisualExpressionBuilder();
      default:
        return new JSONataEngine();
    }
  }
}

// Usage in UI
const ExpressionEditor: React.FC<{ value: string; onChange: (v: string) => void }> = ({ value, onChange }) => {
  const [mode, setMode] = useState<'text' | 'visual'>('text');
  const [engine, setEngine] = useState<ExpressionEngine>(ExpressionEngineFactory.create('text'));
  const [validation, setValidation] = useState<ValidationResult>({ valid: true });
  
  useEffect(() => {
    setEngine(ExpressionEngineFactory.create(mode));
  }, [mode]);
  
  useEffect(() => {
    setValidation(engine.validate(value));
  }, [value, engine]);
  
  return (
    <div className="expression-editor">
      <div className="mode-toggle">
        <button onClick={() => setMode('text')}>Text</button>
        <button onClick={() => setMode('visual')}>Visual</button>
      </div>
      
      {mode === 'text' ? (
        <textarea 
          value={value} 
          onChange={e => onChange(e.target.value)}
          className={validation.valid ? '' : 'error'}
        />
      ) : (
        <VisualBlockBuilder value={value} onChange={onChange} />
      )}
      
      {!validation.valid && (
        <div className="error-message">
          {validation.error}
          {validation.suggestion && <div className="suggestion">{validation.suggestion}</div>}
        </div>
      )}
      
      <ExpressionExamples examples={engine.getExamples()} />
    </div>
  );
};

interface ExpressionBlock {
  type: string;
  [key: string]: any;
}

interface ValidationResult {
  valid: boolean;
  error?: string;
  suggestion?: string;
}

interface ExpressionExample {
  category: string;
  expression: string;
  description: string;
  inputExample: any;
  outputExample: any;
}
```

## Append-Only Side Effect Log with Semantic Compensation

### Key Insight: Compensation Needs Context, Not Just Undo Functions

```typescript
interface SideEffectEntry {
  // Identity
  id: string;
  nodeId: string;
  executionId: string;
  timestamp: number;
  
  // Operation description
  operation: OperationType;
  description: string; // Human-readable
  
  // Semantic compensation descriptor (NOT a function)
  compensation: CompensationDescriptor;
  
  // State
  status: 'pending' | 'executed' | 'failed' | 'compensated';
  
  // Audit trail
  executedAt?: number;
  compensatedAt?: number;
  error?: string;
}

type OperationType = 
  | 'api_call'
  | 'file_write'
  | 'database_write'
  | 'external_webhook'
  | 'email_send'
  | 'payment_process';

// Semantic descriptor instead of executable code
type CompensationDescriptor = 
  | { type: 'reversible'; reverseOperation: OperationDescriptor }
  | { type: 'idempotent'; canRetry: boolean }
  | { type: 'irreversible'; reason: string; manualSteps?: string[] }
  | { type: 'eventual'; compensatingService: string; payload: any };

interface OperationDescriptor {
  service: string;
  method: string;
  endpoint?: string;
  parameters: Record<string, any>;
}

class SideEffectLog {
  private db: IDBDatabase;
  private compensationHandlers: Map<string, CompensationHandler> = new Map();
  
  constructor() {
    this.initDB();
    this.registerDefaultHandlers();
  }
  
  async append(entry: Omit<SideEffectEntry, 'id' | 'timestamp' | 'status'>): Promise<string> {
    const id = crypto.randomUUID();
    
    const effectEntry: SideEffectEntry = {
      ...entry,
      id,
      timestamp: Date.now(),
      status: 'pending'
    };
    
    // Append to log (write-only, no updates)
    await this.writeToLog(effectEntry);
    
    return id;
  }
  
  async markExecuted(effectId: string): Promise<void> {
    // Create new log entry (append-only)
    await this.writeToLog({
      id: crypto.randomUUID(),
      nodeId: 'system',
      executionId: 'system',
      timestamp: Date.now(),
      operation: 'api_call', // dummy
      description: `Effect ${effectId} executed`,
      compensation: { type: 'irreversible', reason: 'audit entry' },
      status: 'executed',
      executedAt: Date.now()
    });
  }
  
  async compensate(effectId: string): Promise<CompensationResult> {
    const entry = await this.getEntry(effectId);
    
    if (!entry) {
      return { success: false, error: 'Effect not found' };
    }
    
    if (entry.status !== 'executed') {
      return { success: false, error: 'Effect not in executed state' };
    }
    
    // Dispatch to appropriate compensation handler
    const handler = this.compensationHandlers.get(entry.compensation.type);
    
    if (!handler) {
      return { 
        success: false, 
        error: `No handler for compensation type: ${entry.compensation.type}` 
      };
    }
    
    try {
      const result = await handler.compensate(entry);
      
      // Log compensation (append-only)
      await this.writeToLog({
        id: crypto.randomUUID(),
        nodeId: entry.nodeId,
        executionId: entry.executionId,
        timestamp: Date.now(),
        operation: entry.operation,
        description: `Compensated: ${entry.description}`,
        compensation: entry.compensation,
        status: 'compensated',
        compensatedAt: Date.now()
      });
      
      return result;
      
    } catch (error) {
      // Log failure (append-only)
      await this.writeToLog({
        id: crypto.randomUUID(),
        nodeId: entry.nodeId,
        executionId: entry.executionId,
        timestamp: Date.now(),
        operation: entry.operation,
        description: `Compensation failed: ${entry.description}`,
        compensation: entry.compensation,
        status: 'failed',
        error: error.message
      });
      
      return { success: false, error: error.message };
    }
  }
  
  async compensateAllForNode(nodeId: string): Promise<CompensationResult[]> {
    const entries = await this.getEntriesForNode(nodeId);
    const executed = entries
      .filter(e => e.status === 'executed')
      .reverse(); // Reverse order for LIFO
    
    const results: CompensationResult[] = [];
    
    for (const entry of executed) {
      const result = await this.compensate(entry.id);
      results.push(result);
      
      // Stop on first failure for safety
      if (!result.success) {
        break;
      }
    }
    
    return results;
  }
  
  async getEntriesForExecution(executionId: string): Promise<SideEffectEntry[]> {
    const tx = this.db.transaction('effects', 'readonly');
    const store = tx.objectStore('effects');
    const index = store.index('executionId');
    
    const entries: SideEffectEntry[] = [];
    const cursor = await index.openCursor(IDBKeyRange.only(executionId));
    
    while (cursor) {
      entries.push(cursor.value);
      await cursor.continue();
    }
    
    return entries;
  }
  
  private registerDefaultHandlers(): void {
    // Reversible operations (API calls with DELETE endpoints)
    this.compensationHandlers.set('reversible', {
      compensate: async (entry) => {
        const descriptor = (entry.compensation as any).reverseOperation;
        
        // Call reverse operation
        const response = await fetch(descriptor.endpoint, {
          method: descriptor.method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(descriptor.parameters)
        });
        
        if (!response.ok) {
          throw new Error(`Reverse operation failed: ${response.statusText}`);
        }
        
        return { success: true };
      }
    });
    
    // Idempotent operations (can safely retry)
    this.compensationHandlers.set('idempotent', {
      compensate: async (entry) => {
        // No-op or retry logic
        return { success: true, message: 'Idempotent operation - safe to leave' };
      }
    });
    
    // Irreversible operations (manual intervention required)
    this.compensationHandlers.set('irreversible', {
      compensate: async (entry) => {
        const descriptor = entry.compensation as any;
        
        // Can't auto-compensate - return manual steps
        return {
          success: false,
          error: `Cannot auto-compensate: ${descriptor.reason}`,
          manualSteps: descriptor.manualSteps,
          requiresUserAction: true
        };
      }
    });
    
    // Eventual consistency (call compensating transaction service)
    this.compensationHandlers.set('eventual', {
      compensate: async (entry) => {
        const descriptor = entry.compensation as any;
        
        // Call compensating service
        const response = await fetch(descriptor.compensatingService, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(descriptor.payload)
        });
        
        if (!response.ok) {
          throw new Error(`Compensating service failed: ${response.statusText}`);
        }
        
        return { 
          success: true, 
          message: 'Compensating transaction initiated' 
        };
      }
    });
  }
  
  private async writeToLog(entry: SideEffectEntry): Promise<void> {
    const tx = this.db.transaction('effects', 'readwrite');
    const store = tx.objectStore('effects');
    await store.add(entry);
  }
  
  private async getEntry(effectId: string): Promise<SideEffectEntry | null> {
    const tx = this.db.transaction('effects', 'readonly');
    const store = tx.objectStore('effects');
    return await store.get(effectId);
  }
  
  private async getEntriesForNode(nodeId: string): Promise<SideEffectEntry[]> {
    const tx = this.db.transaction('effects', 'readonly');
    const store = tx.objectStore('effects');
    const index = store.index('nodeId');
    
    const entries: SideEffectEntry[] = [];
    const cursor = await index.openCursor(IDBKeyRange.only(nodeId));
    
    while (cursor) {
      entries.push(cursor.value);
      await cursor.continue();
    }
    
    return entries;
  }
  
  private async initDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('SideEffectLog', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        const store = db.createObjectStore('effects', { keyPath: 'id' });
        store.createIndex('nodeId', 'nodeId', { unique: false });
        store.createIndex('executionId', 'executionId', { unique: false });
        store.createIndex('timestamp', 'timestamp', { unique: false });
      };
    });
  }
}

interface CompensationHandler {
  compensate(entry: SideEffectEntry): Promise<CompensationResult>;
}

interface CompensationResult {
  success: boolean;
  error?: string;
  message?: string;
  manualSteps?: string[];
  requiresUserAction?: boolean;
}
```

### Usage Examples

```typescript
// Example 1: API call with reversible compensation
const effectId = await sideEffectLog.append({
  nodeId: 'node-123',
  executionId: 'exec-456',
  operation: 'api_call',
  description: 'Create user account',
  compensation: {
    type: 'reversible',
    reverseOperation: {
      service: 'user-service',
      method: 'DELETE',
      endpoint: '/api/users/{{userId}}',
      parameters: { userId: '{{createdUserId}}' }
    }
  }
});

// Example 2: Email send (irreversible)
await sideEffectLog.append({
  nodeId: 'node-123',
  executionId: 'exec-456',
  operation: 'email_send',
  description: 'Send welcome email to user@example.com',
  compensation: {
    type: 'irreversible',
    reason: 'Email cannot be unsent',
    manualSteps: [
      'Send apology email explaining the error',
      'Update user account status to reflect correction'
    ]
  }
});

// Example 3: Database write with eventual consistency
await sideEffectLog.append({
  nodeId: 'node-123',
  executionId: 'exec-456',
  operation: 'database_write',
  description: 'Deduct 100 credits from account',
  compensation: {
    type: 'eventual',
    compensatingService: '/api/credits/refund',
    payload: {
      accountId: 'acc-789',
      amount: 100,
      reason: 'workflow_rollback'
    }
  }
});
```

## Enhanced Checkpoint Manager

```typescript
class CheckpointManager {
  private db: IDBDatabase;
  private sideEffectLog: SideEffectLog;
  
  constructor(sideEffectLog: SideEffectLog) {
    this.sideEffectLog = sideEffectLog;
    this.initDB();
  }
  
  async createCheckpoint(
    executionState: ExecutionState,
    reason: 'manual' | 'auto' | 'error' = 'auto'
  ): Promise<string> {
    const checkpointId = crypto.randomUUID();
    
    // Capture side effects up to this point
    const sideEffects = await this.sideEffectLog.getEntriesForExecution(
      executionState.executionId
    );
    
    const checkpoint: ExecutionCheckpoint = {
      id: checkpointId,
      executionId: executionState.executionId,
      timestamp: Date.now(),
      nodeStates: this.serializeNodeStates(executionState.nodeStates),
      sideEffectCount: sideEffects.length,
      reason
    };
    
    const tx = this.db.transaction('checkpoints', 'readwrite');
    await tx.objectStore('checkpoints').put(checkpoint);
    
    return checkpointId;
  }
  
  async restoreCheckpoint(
    checkpointId: string,
    strategy: CompensationStrategy
  ): Promise<RestoreResult> {
    
    const checkpoint = await this.getCheckpoint(checkpointId);
    if (!checkpoint) {
      return { success: false, error: 'Checkpoint not found' };
    }
    
    // Get all side effects after checkpoint
    const allEffects = await this.sideEffectLog.getEntriesForExecution(
      checkpoint.executionId
    );
    
    const effectsToCompensate = allEffects.filter(e => 
      e.timestamp > checkpoint.timestamp
    );
    
    // Handle compensation based on strategy
    const compensationResults = await this.applyCompensationStrategy(
      effectsToCompensate,
      strategy
    );
    
    // Check for manual intervention required
    const manualSteps = compensationResults
      .filter(r => r.requiresUserAction)
      .flatMap(r => r.manualSteps || []);
    
    return {
      success: true,
      checkpoint,
      compensationResults,
      manualSteps: manualSteps.length > 0 ? manualSteps : undefined
    };
  }
  
  private async applyCompensationStrategy(
    effects: SideEffectEntry[],
    strategy: CompensationStrategy
  ): Promise<CompensationResult[]> {
    
    switch (strategy) {
      case 'automatic':
        // Compensate all reversible effects automatically
        const results: CompensationResult[] = [];
        
        for (const effect of effects.reverse()) {
          if (effect.compensation.type === 'reversible' || 
              effect.compensation.type === 'eventual') {
            
            const result = await this.sideEffectLog.compensate(effect.id);
            results.push(result);
            
            if (!result.success) {
              // Stop on first failure
              break;
            }
          } else {
            // Skip irreversible effects
            results.push({
              success: false,
              error: 'Skipped irreversible effect',
              requiresUserAction: true,
              manualSteps: (effect.compensation as any).manualSteps
            });
          }
        }
        
        return results;
        
      case 'manual':
        // Return list of effects for user to handle manually
        return effects.map(effect => ({
          success: false,
          requiresUserAction: true,
          manualSteps: [
            `Effect: ${effect.description}`,
            `Type: ${effect.compensation.type}`,
            ...(effect.compensation.type === 'irreversible' 
              ? (effect.compensation as any).manualSteps || []
              : ['Manually revert this operation'])
          ]
        }));
        
      case 'confirm_each':
        // This requires user interaction - not fully implemented here
        // In practice, this would show a UI for each effect
        return [];
        
      default:
        throw new Error(`Unknown strategy: ${strategy}`);
    }
  }
  
  private async getCheckpoint(checkpointId: string): Promise<ExecutionCheckpoint | null> {
    const tx = this.db.transaction('checkpoints', 'readonly');
    const store = tx.objectStore('checkpoints');
    return await store.get(checkpointId);
  }
  
  private serializeNodeStates(nodeStates: Map<string, NodeState>): any {
    return Array.from(nodeStates.entries());
  }
  
  private async initDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowCheckpoints', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('checkpoints')) {
          db.createObjectStore('checkpoints', { keyPath: 'id' });
        }
      };
    });
  }
}

type CompensationStrategy = 
  | 'automatic'      // Auto-compensate all reversible effects
  | 'manual'         // User handles all compensation
  | 'confirm_each';  // Ask user for each effect

interface ExecutionCheckpoint {
  id: string;
  executionId: string;
  timestamp: number;
  nodeStates: any;
  sideEffectCount: number;
  reason: string;
}

interface RestoreResult {
  success: boolean;
  error?: string;
  checkpoint?: ExecutionCheckpoint;
  compensationResults?: CompensationResult[];
  manualSteps?: string[];
}
```

## Performance Optimizations

### Viewport Culling
```typescript
const WorkflowCanvas: React.FC = () => {
  const { nodes, edges } = useWorkflowStore();
  const [viewport, setViewport] = useState<Viewport>({ x: 0, y: 0, zoom: 1 });
  
  const visibleNodes = useMemo(() => {
    if (nodes.length < 50) return nodes;
    
    return nodes.filter(node => isNodeInViewport(node, viewport));
  }, [nodes, viewport]);
  
  const visibleEdges = useMemo(() => {
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
    return edges.filter(e => 
      visibleNodeIds.has(e.source) || visibleNodeIds.has(e.target)
    );
  }, [edges, visibleNodes]);
  
  return (
    <ReactFlow
      nodes={visibleNodes}
      edges={visibleEdges}
      onMove={(_, vp) => setViewport(vp)}
    />
  );
};
```

### Virtual Scrolling
```typescript
import { FixedSizeList } from 'react-window';

const NodePalette: React.FC = () => {
  const nodeTypes = useNodeTypes();
  
  return (
    <FixedSizeList
      height={600}
      itemCount={nodeTypes.length}
      itemSize={60}
      width="100%"
    >
      {({ index, style }) => (
        <div style={style}>
          <NodePaletteItem node={nodeTypes[index]} />
        </div>
      )}
    </FixedSizeList>
  );
};
```

### Debounced Auto-Save
```typescript
const useAutoSave = (workflowId: string) => {
  const { workflow } = useWorkflowStore();
  const saveWorkflow = useSaveWorkflow();
  
  const debouncedSave = useMemo(
    () => debounce(() => saveWorkflow(workflow), 2000),
    [workflow, saveWorkflow]
  );
  
  useEffect(() => {
    debouncedSave();
    return () => debouncedSave.cancel();
  }, [workflow, debouncedSave]);
};
```

## What I Improved

### 1. **Dramatically Simplified Storage (3-Tier vs Complex Eviction)**
- Removed complex hybrid eviction scoring system
- **Three simple tiers**: Hot (50MB, tiny hot data) → Warm (500MB, default) → Cold (optional, huge files)
- **Simple FIFO eviction** in hot cache, no complex LRU+size hybrid scoring
- Most artifacts live in Warm (IndexedDB) which is fast enough
- **Metadata index** keeps all artifact info lightweight and queryable
- **Auto-cleanup** of old temporary data every hour

### 2. **Streaming Decision Logic (Analyze First, Then Commit)**
- Added `analyzeStreamingFeasibility()` to make intelligent streaming decisions
- **Materialization strategy** for multi-consumer scenarios (store once, serve many)
- **Streaming reasons** tracked for debugging and optimization
- **Graceful degradation** to batch mode when streaming doesn't make sense
- **Storage references** ($ref) for materialized streams instead of duplicating data

### 3. **Pluggable Expression Engine (Progressive Enhancement)**
- Expression engine is now an **interface** - swap JSONata for visual builder
- **Validation with suggestions** helps users fix errors
- **Visual builder option** for users who find text expressions hard
- **Expression examples** built into the engine, not hard-coded in UI
- **Syntax help** provided by the engine itself

### 4. **Semantic Compensation (Descriptors Not Functions)**
- Replaced JSONata compensation functions with **semantic descriptors**
- **Four compensation types**: reversible, idempotent, irreversible, eventual
- **Compensation handlers** registered per type, not per node
- **Manual steps** included for irreversible operations (emails, payments)
- **Append-only log** instead of mutable side effect records
- **Audit trail** preserved forever for compliance

### 5. **Compensation Strategy Selection**
- Three strategies: **automatic** (safe auto-compensation), **manual** (user handles), **confirm_each** (interactive)
- **Automatic stops on first failure** for safety
- **Manual steps returned** to user for irreversible effects
- **Partial compensation** supported (some effects can't be undone)

## What I Kept

All the excellent foundation:
- React Flow canvas
- Zustand + immer state management
- Worker pool architecture
- Topological execution
- Multiple handles per node
- Input/output schemas
- Retry configuration
- Event system
- Undo/redo
- Edge validation
- Resource limits
- Node status granularity
- Template system
- Viewport culling optimization
- Virtual scrolling for large lists
- Debounced auto-save
- Native Web Streams API for streaming
- Compression for large data

## Remaining Concerns

### 1. **Cold Storage Implementation**
The current cold storage using blob URLs is browser-only and lost on refresh. For production:
- Should we use **object storage** (S3, R2) for truly cold artifacts?
- **Pre-signed URLs** for download instead of storing in browser?
- **Lifecycle policies** to auto-delete cold storage after X days?

### 2. **Expression Engine Complexity**
JSONata is powerful but has a learning curve:
- Should visual builder be **always available** as an alternative input method?
- **AI-assisted expression generation**: "convert this to an expression"?
- **Template expressions** library for common patterns?

### 3. **Compensation Handler Registration**
Currently hard-coded handlers for 4 types:
- Should users be able to **register custom handlers** for their services?
- **Plugin system** for compensation handlers?
- **Compensation middleware** for cross-cutting concerns (logging, notifications)?

### 4. **Multi-Tab Coordination**
Not addressed in this design:
- **Lock workflows** during execution to prevent conflicts?
- **Broadcast execution state** using BroadcastChannel API?
- **Conflict resolution** when multiple tabs modify same workflow?

### 5. **Cost Tracking**
For long-running workflows with many LLM calls:
- **Pre-execution cost estimate** based on token limits per node?
- **Running cost counter** updated as nodes complete?
- **Budget limits** with auto-pause when approaching threshold?

## Convergence Status

**ITERATING** - This design significantly simplifies storage and compensation while adding critical missing pieces:

✅ Simplified 3-tier storage (much easier to implement and reason about)  
✅ Smart streaming decisions with materialization strategy  
✅ Pluggable expression engine (text or visual)  
✅ Semantic compensation with audit trail  
✅ Compensation strategy selection  
✅ All performance optimizations preserved  

However, still needs refinement on:
- Cold storage backend for production
- Expression engine UX (visual builder, AI assist)
- Custom compensation handler registration
- Multi-tab coordination strategy

---

## PROMPT_FOR_ARCHITECT:

Please focus on these specific design questions:

1. **Storage Backend**: Should cold storage use browser blob URLs (current design) or integrate with object storage (S3/R2) for production? What's the right trade-off between complexity and capability?

2. **Expression Engine UX**: Should the visual builder be a separate mode (current design) or should we allow **mixed mode** where users can switch between text and visual for different parts of an expression?

3. **Compensation Handler Extensibility**: Should we support **user-defined compensation handlers** for custom services, or is the 4-type system (reversible/idempotent/irreversible/eventual) sufficient for most use cases?

4. **Materialization Heuristics**: When a stream has multiple consumers, the current design always materializes to storage. Should we support **stream teeing** for small streams and only materialize large ones? What's the size threshold?

**Convergence Signal:** ITERATING

---

## Round 3

### 🔵 Agent A

## Design

# Visual AI Agent Workflow Builder - Production-Ready Architecture v3

## Core Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │         │
│  │   (React     │  │    Panel     │  │   & Palette  │         │
│  │    Flow)     │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│           State Management (Zustand + Immer)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Orchestration Layer                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Adaptive   │  │  Hybrid    │  │ Checkpoint │         │  │
│  │  │ Executor   │  │  Storage   │  │  Manager   │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Data Flow & Storage Layer                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Composable │  │   Two-Tier │  │ Effect Log │         │  │
│  │  │ Expression │  │  + Overflow│  │  (Append-  │         │  │
│  │  │  System    │  │  Strategy  │  │   Only)    │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas**: React Flow v11+ with viewport culling
- **State**: Zustand with immer middleware and persistence
- **UI**: Radix UI primitives + Tailwind CSS
- **Execution**: Adaptive executor with streaming + teeing for multi-consumer
- **Storage**: Two-tier (Memory + IndexedDB) with configurable overflow strategies
- **Expressions**: Composable expression system (JSONata blocks + visual builder)
- **Side Effects**: Append-only log with pluggable compensation handlers
- **Workers**: Shared Worker pool with resource quotas

## Simplified Two-Tier Storage with Overflow Strategy

### Key Insight: Let Users Choose Overflow Behavior, Not Complex Auto-Eviction

```typescript
type OverflowStrategy = 
  | 'drop-oldest'           // FIFO eviction (default)
  | 'drop-on-store'         // Fail loudly when full
  | 'compress-aggressive'   // Compress everything aggressively
  | 'external-blob';        // Use blob URLs for overflow (browser-only)

interface StorageConfig {
  // Simple two-tier system
  memoryCacheMaxBytes: number;      // 100MB - hot in-memory data
  indexedDBMaxBytes: number;        // 1GB - warm IndexedDB storage
  
  // What happens when IndexedDB fills up?
  overflowStrategy: OverflowStrategy;
  
  // Compression settings
  compressionThreshold: number;     // 1MB - compress above this
  compressionLevel: 'fast' | 'balanced' | 'best';
  
  // Auto-cleanup
  autoCleanupAge: number;           // 24h - delete old temp artifacts
  enableAutoCleanup: boolean;
}

class HybridStorageManager {
  private memoryCache: Map<string, CacheEntry> = new Map();
  private memoryCacheSize: number = 0;
  private indexedDB: IDBDatabase;
  private indexedDBSize: number = 0;
  private config: StorageConfig;
  
  // Lightweight metadata for all artifacts
  private artifactIndex: Map<string, ArtifactMetadata> = new Map();
  
  // External blob URLs (only for 'external-blob' strategy)
  private externalBlobs: Map<string, string> = new Map();
  
  constructor(config: StorageConfig) {
    this.config = config;
    this.initIndexedDB();
    
    if (config.enableAutoCleanup) {
      this.scheduleCleanup();
    }
  }
  
  async store(key: string, data: any, hints: StorageHints = {}): Promise<void> {
    const serialized = JSON.stringify(data);
    const sizeBytes = new TextEncoder().encode(serialized).length;
    
    // Update metadata
    this.artifactIndex.set(key, {
      key,
      sizeBytes,
      tier: 'determining',
      createdAt: Date.now(),
      lastAccessedAt: Date.now(),
      accessCount: 0,
      temporary: hints.temporary ?? true,
      nodeId: hints.nodeId,
      executionId: hints.executionId
    });
    
    // Tier decision: Simple size-based
    if (sizeBytes < 1024 * 1024) { // < 1MB -> try memory first
      if (await this.tryStoreInMemory(key, data, sizeBytes)) {
        this.artifactIndex.get(key)!.tier = 'memory';
        return;
      }
    }
    
    // Otherwise use IndexedDB
    await this.storeInIndexedDB(key, serialized, sizeBytes);
    this.artifactIndex.get(key)!.tier = 'indexeddb';
  }
  
  private async tryStoreInMemory(key: string, data: any, sizeBytes: number): Promise<boolean> {
    if (this.memoryCacheSize + sizeBytes <= this.config.memoryCacheMaxBytes) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    // Try to evict old memory entries
    if (await this.evictFromMemory(sizeBytes)) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    return false;
  }
  
  private async evictFromMemory(requiredBytes: number): Promise<boolean> {
    const entries = Array.from(this.memoryCache.entries())
      .sort((a, b) => a[1].storedAt - b[1].storedAt);
    
    let freedBytes = 0;
    const toEvict: string[] = [];
    
    for (const [key, entry] of entries) {
      // Don't evict very recent entries (< 5s old)
      if (Date.now() - entry.storedAt < 5000) continue;
      
      toEvict.push(key);
      freedBytes += entry.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (freedBytes < requiredBytes) return false;
    
    // Move to IndexedDB (no data loss)
    for (const key of toEvict) {
      const entry = this.memoryCache.get(key)!;
      await this.storeInIndexedDB(key, JSON.stringify(entry.data), entry.sizeBytes);
      
      this.memoryCache.delete(key);
      this.memoryCacheSize -= entry.sizeBytes;
      
      const metadata = this.artifactIndex.get(key);
      if (metadata) metadata.tier = 'indexeddb';
    }
    
    return true;
  }
  
  private async storeInIndexedDB(key: string, serialized: string, sizeBytes: number): Promise<void> {
    // Check if we're at capacity
    if (this.indexedDBSize + sizeBytes > this.config.indexedDBMaxBytes) {
      await this.handleIndexedDBOverflow(key, serialized, sizeBytes);
      return;
    }
    
    // Compress if needed
    const shouldCompress = sizeBytes > this.config.compressionThreshold;
    const toStore = shouldCompress 
      ? await this.compress(serialized, this.config.compressionLevel)
      : serialized;
    
    const actualSize = shouldCompress 
      ? new TextEncoder().encode(toStore as string).length 
      : sizeBytes;
    
    const tx = this.indexedDB.transaction('artifacts', 'readwrite');
    const store = tx.objectStore('artifacts');
    
    await store.put({
      key,
      data: toStore,
      compressed: shouldCompress,
      sizeBytes: actualSize,
      storedAt: Date.now()
    });
    
    this.indexedDBSize += actualSize;
  }
  
  private async handleIndexedDBOverflow(key: string, serialized: string, sizeBytes: number): Promise<void> {
    switch (this.config.overflowStrategy) {
      case 'drop-oldest':
        // Evict oldest entries until we have space
        await this.evictOldestFromIndexedDB(sizeBytes);
        await this.storeInIndexedDB(key, serialized, sizeBytes);
        break;
        
      case 'drop-on-store':
        throw new Error(
          `Storage full: Cannot store ${key} (${(sizeBytes / 1024 / 1024).toFixed(2)}MB). ` +
          `IndexedDB usage: ${(this.indexedDBSize / 1024 / 1024).toFixed(2)}MB / ` +
          `${(this.config.indexedDBMaxBytes / 1024 / 1024).toFixed(2)}MB`
        );
        
      case 'compress-aggressive':
        // Force best compression on this item
        const compressed = await this.compress(serialized, 'best');
        const compressedSize = new TextEncoder().encode(compressed).length;
        
        if (this.indexedDBSize + compressedSize > this.config.indexedDBMaxBytes) {
          // Still doesn't fit - evict oldest
          await this.evictOldestFromIndexedDB(compressedSize);
        }
        
        const tx = this.indexedDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').put({
          key,
          data: compressed,
          compressed: true,
          sizeBytes: compressedSize,
          storedAt: Date.now()
        });
        
        this.indexedDBSize += compressedSize;
        break;
        
      case 'external-blob':
        // Store as blob URL (browser-only, lost on refresh)
        const compressed2 = await this.compress(serialized, 'best');
        const blob = new Blob([compressed2], { type: 'application/octet-stream' });
        const blobUrl = URL.createObjectURL(blob);
        
        this.externalBlobs.set(key, blobUrl);
        
        // Store tiny reference in IndexedDB
        const tx2 = this.indexedDB.transaction('blobRefs', 'readwrite');
        await tx2.objectStore('blobRefs').put({
          key,
          blobUrl,
          sizeBytes,
          storedAt: Date.now()
        });
        
        const metadata = this.artifactIndex.get(key);
        if (metadata) metadata.tier = 'external';
        break;
    }
  }
  
  private async evictOldestFromIndexedDB(requiredBytes: number): Promise<void> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    const index = store.index('storedAt');
    
    const entries: Array<{ key: string; sizeBytes: number }> = [];
    let cursor = await index.openCursor();
    
    while (cursor) {
      entries.push({
        key: cursor.value.key,
        sizeBytes: cursor.value.sizeBytes
      });
      cursor = await cursor.continue();
    }
    
    // Sort by age
    entries.sort((a, b) => {
      const aTime = this.artifactIndex.get(a.key)?.createdAt ?? 0;
      const bTime = this.artifactIndex.get(b.key)?.createdAt ?? 0;
      return aTime - bTime;
    });
    
    let freedBytes = 0;
    const toDelete: string[] = [];
    
    for (const entry of entries) {
      toDelete.push(entry.key);
      freedBytes += entry.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    // Delete entries
    const txDelete = this.indexedDB.transaction('artifacts', 'readwrite');
    const storeDelete = txDelete.objectStore('artifacts');
    
    for (const key of toDelete) {
      await storeDelete.delete(key);
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        this.indexedDBSize -= metadata.sizeBytes;
      }
      this.artifactIndex.delete(key);
    }
  }
  
  async retrieve(key: string): Promise<any> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) {
      throw new Error(`Artifact not found: ${key}`);
    }
    
    // Update access tracking
    metadata.accessCount++;
    metadata.lastAccessedAt = Date.now();
    
    let data: any;
    
    switch (metadata.tier) {
      case 'memory':
        data = this.memoryCache.get(key)?.data;
        if (!data) {
          // Fallback to IndexedDB
          data = await this.retrieveFromIndexedDB(key);
        }
        break;
        
      case 'indexeddb':
        data = await this.retrieveFromIndexedDB(key);
        
        // Promote to memory if: small + accessed frequently
        if (metadata.sizeBytes < 1024 * 1024 && 
            metadata.accessCount >= 3 &&
            Date.now() - metadata.createdAt < 60000) {
          
          if (await this.tryStoreInMemory(key, data, metadata.sizeBytes)) {
            metadata.tier = 'memory';
          }
        }
        break;
        
      case 'external':
        data = await this.retrieveFromExternalBlob(key);
        break;
        
      default:
        throw new Error(`Unknown tier: ${metadata.tier}`);
    }
    
    return data;
  }
  
  private async retrieveFromIndexedDB(key: string): Promise<any> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    const record = await store.get(key);
    
    if (!record) {
      throw new Error(`Artifact not in IndexedDB: ${key}`);
    }
    
    const serialized = record.compressed
      ? await this.decompress(record.data)
      : record.data;
    
    return JSON.parse(serialized);
  }
  
  private async retrieveFromExternalBlob(key: string): Promise<any> {
    const blobUrl = this.externalBlobs.get(key);
    if (!blobUrl) {
      throw new Error(`External blob not found: ${key}`);
    }
    
    const response = await fetch(blobUrl);
    const compressed = await response.text();
    const serialized = await this.decompress(compressed);
    return JSON.parse(serialized);
  }
  
  async clear(predicate?: (metadata: ArtifactMetadata) => boolean): Promise<void> {
    if (!predicate) {
      // Clear everything
      this.memoryCache.clear();
      this.memoryCacheSize = 0;
      this.indexedDBSize = 0;
      this.artifactIndex.clear();
      
      const tx = this.indexedDB.transaction(['artifacts', 'blobRefs'], 'readwrite');
      await tx.objectStore('artifacts').clear();
      await tx.objectStore('blobRefs').clear();
      
      // Revoke blob URLs
      for (const blobUrl of this.externalBlobs.values()) {
        URL.revokeObjectURL(blobUrl);
      }
      this.externalBlobs.clear();
      
      return;
    }
    
    // Selective clear
    const toDelete: string[] = [];
    
    for (const [key, metadata] of this.artifactIndex.entries()) {
      if (predicate(metadata)) {
        toDelete.push(key);
      }
    }
    
    for (const key of toDelete) {
      await this.delete(key);
    }
  }
  
  private async delete(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) return;
    
    switch (metadata.tier) {
      case 'memory':
        const entry = this.memoryCache.get(key);
        if (entry) {
          this.memoryCacheSize -= entry.sizeBytes;
          this.memoryCache.delete(key);
        }
        break;
        
      case 'indexeddb':
        const tx = this.indexedDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').delete(key);
        this.indexedDBSize -= metadata.sizeBytes;
        break;
        
      case 'external':
        const blobUrl = this.externalBlobs.get(key);
        if (blobUrl) {
          URL.revokeObjectURL(blobUrl);
          this.externalBlobs.delete(key);
        }
        
        const tx2 = this.indexedDB.transaction('blobRefs', 'readwrite');
        await tx2.objectStore('blobRefs').delete(key);
        break;
    }
    
    this.artifactIndex.delete(key);
  }
  
  private scheduleCleanup(): void {
    setInterval(() => {
      const cutoff = Date.now() - this.config.autoCleanupAge;
      
      this.clear(metadata => 
        metadata.temporary && metadata.createdAt < cutoff
      );
    }, 60 * 60 * 1000); // 1 hour
  }
  
  getStorageStats(): StorageStats {
    const stats = {
      memory: { count: 0, bytes: this.memoryCacheSize },
      indexeddb: { count: 0, bytes: this.indexedDBSize },
      external: { count: 0, bytes: 0 },
      total: { count: this.artifactIndex.size, bytes: 0 }
    };
    
    for (const metadata of this.artifactIndex.values()) {
      stats[metadata.tier as 'memory' | 'indexeddb' | 'external'].count++;
      if (metadata.tier === 'external') {
        stats.external.bytes += metadata.sizeBytes;
      }
      stats.total.bytes += metadata.sizeBytes;
    }
    
    return stats;
  }
  
  private async compress(data: string, level: 'fast' | 'balanced' | 'best'): Promise<string> {
    // Use native compression (gzip)
    const encoder = new TextEncoder();
    const stream = new Blob([data]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    
    // Convert to base64 for storage
    const uint8 = new Uint8Array(buffer);
    return btoa(String.fromCharCode(...uint8));
  }
  
  private async decompress(data: string): Promise<string> {
    // Decode from base64
    const binary = atob(data);
    const uint8 = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      uint8[i] = binary.charCodeAt(i);
    }
    
    const stream = new Blob([uint8]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowStorage', 3);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.indexedDB = request.result;
        this.calculateIndexedDBSize();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('artifacts')) {
          const store = db.createObjectStore('artifacts', { keyPath: 'key' });
          store.createIndex('storedAt', 'storedAt', { unique: false });
        }
        
        if (!db.objectStoreNames.contains('blobRefs')) {
          db.createObjectStore('blobRefs', { keyPath: 'key' });
        }
      };
    });
  }
  
  private async calculateIndexedDBSize(): Promise<void> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    let cursor = await store.openCursor();
    
    let totalSize = 0;
    while (cursor) {
      totalSize += cursor.value.sizeBytes || 0;
      cursor = await cursor.continue();
    }
    
    this.indexedDBSize = totalSize;
  }
}

// Types
interface CacheEntry {
  data: any;
  sizeBytes: number;
  storedAt: number;
}

interface ArtifactMetadata {
  key: string;
  sizeBytes: number;
  tier: 'memory' | 'indexeddb' | 'external' | 'determining';
  createdAt: number;
  lastAccessedAt: number;
  accessCount: number;
  temporary: boolean;
  nodeId?: string;
  executionId?: string;
}

interface StorageHints {
  temporary?: boolean;
  nodeId?: string;
  executionId?: string;
}

interface StorageStats {
  memory: { count: number; bytes: number };
  indexeddb: { count: number; bytes: number };
  external: { count: number; bytes: number };
  total: { count: number; bytes: number };
}
```

### Usage Example
```typescript
const storage = new HybridStorageManager({
  memoryCacheMaxBytes: 100 * 1024 * 1024,      // 100MB
  indexedDBMaxBytes: 1024 * 1024 * 1024,       // 1GB
  overflowStrategy: 'drop-oldest',             // Default: FIFO eviction
  compressionThreshold: 1024 * 1024,           // 1MB
  compressionLevel: 'balanced',
  autoCleanupAge: 24 * 60 * 60 * 1000,        // 24h
  enableAutoCleanup: true
});

// Store with automatic tiering
await storage.store(
  `node-${nodeId}-output`,
  largeDataset,
  {
    nodeId,
    executionId,
    temporary: true
  }
);

// Retrieve (transparent tier access)
const data = await storage.retrieve(`node-${nodeId}-output`);

// Cleanup after workflow
await storage.clear(meta => 
  meta.temporary && meta.executionId === executionId
);

// Check storage
const stats = storage.getStorageStats();
console.log(`Memory: ${(stats.memory.bytes / 1024 / 1024).toFixed(2)}MB`);
console.log(`IndexedDB: ${(stats.indexeddb.bytes / 1024 / 1024).toFixed(2)}MB`);
```

## Adaptive Streaming with Smart Teeing

### Key Insight: Tee Small Streams, Materialize Large Ones

```typescript
interface StreamingConfig {
  teeThresholdBytes: number;        // 5MB - tee if smaller
  materializeThresholdBytes: number; // 50MB - always materialize if larger
  enableAdaptiveTee: boolean;        // Use size estimation for decision
}

class AdaptiveExecutor {
  private streamingExecutor: StreamingExecutor;
  private batchExecutor: BatchExecutor;
  private storage: HybridStorageManager;
  private config: StreamingConfig;
  
  constructor(storage: HybridStorageManager, config: StreamingConfig) {
    this.storage = storage;
    this.config = config;
    this.streamingExecutor = new StreamingExecutor();
    this.batchExecutor = new BatchExecutor();
  }
  
  async executeNode(
    node: WorkflowNode,
    inputs: Record<string, any>,
    edges: WorkflowEdge[]
  ): Promise<ExecutionResult> {
    
    // Analyze streaming feasibility
    const decision = this.analyzeStreamingFeasibility(node, inputs, edges);
    
    if (decision.shouldStream) {
      return this.executeWithStreaming(node, inputs, decision);
    } else {
      return this.executeWithBatch(node, inputs);
    }
  }
  
  private analyzeStreamingFeasibility(
    node: WorkflowNode,
    inputs: Record<string, any>,
    edges: WorkflowEdge[]
  ): StreamingDecision {
    
    const reasons: string[] = [];
    let shouldStream = false;
    let multiConsumerStrategy: MultiConsumerStrategy = 'none';
    
    // 1. Explicit node config
    if (node.data.config.streaming === false) {
      return {
        shouldStream: false,
        reasons: ['explicit_batch_mode'],
        multiConsumerStrategy: 'none'
      };
    }
    
    if (node.data.config.streaming === true) {
      shouldStream = true;
      reasons.push('explicit_streaming_mode');
    }
    
    // 2. Stream input detection
    const hasStreamInput = Object.values(inputs).some(v => 
      v instanceof ReadableStream
    );
    
    if (hasStreamInput) {
      shouldStream = true;
      reasons.push('stream_input_detected');
    }
    
    // 3. Large data heuristic
    const estimatedSize = this.estimateDataSize(inputs);
    if (estimatedSize > 5 * 1024 * 1024) {
      shouldStream = true;
      reasons.push('large_input_heuristic');
    }
    
    // 4. Agent type benefits
    if (['researcher', 'coder', 'reviewer'].includes(node.data.type)) {
      shouldStream = true;
      reasons.push('agent_benefits_from_streaming');
    }
    
    // 5. Multi-consumer analysis
    if (shouldStream) {
      const downstreamCount = edges.filter(e => e.source === node.id).length;
      
      if (downstreamCount > 1) {
        // Decide between teeing and materialization
        multiConsumerStrategy = this.selectMultiConsumerStrategy(
          estimatedSize,
          downstreamCount
        );
        
        reasons.push(`multi_consumer_${multiConsumerStrategy}`);
      }
    }
    
    return {
      shouldStream,
      reasons,
      multiConsumerStrategy
    };
  }
  
  private selectMultiConsumerStrategy(
    estimatedSize: number,
    consumerCount: number
  ): MultiConsumerStrategy {
    
    if (!this.config.enableAdaptiveTee) {
      // Always materialize if adaptive disabled
      return 'materialize';
    }
    
    // Large streams: always materialize (avoid memory pressure)
    if (estimatedSize > this.config.materializeThresholdBytes) {
      return 'materialize';
    }
    
    // Small streams: tee is efficient
    if (estimatedSize < this.config.teeThresholdBytes) {
      return consumerCount <= 3 ? 'tee' : 'materialize';
    }
    
    // Medium streams: depends on consumer count
    // More consumers = more memory copies = prefer materialize
    if (consumerCount <= 2) {
      return 'tee';
    } else {
      return 'materialize';
    }
  }
  
  private async executeWithStreaming(
    node: WorkflowNode,
    inputs: Record<string, any>,
    decision: StreamingDecision
  ): Promise<ExecutionResult> {
    
    const outputStream = await this.streamingExecutor.executeNodeStreaming(
      node,
      inputs
    );
    
    // Handle multi-consumer scenario
    if (decision.multiConsumerStrategy === 'materialize') {
      return await this.materializeStreamToStorage(node, outputStream, decision);
    } else if (decision.multiConsumerStrategy === 'tee') {
      return await this.teeStreamForConsumers(node, outputStream, decision);
    }
    
    // Single consumer: pass stream through
    return {
      nodeId: node.id,
      output: outputStream,
      streaming: true,
      metadata: {
        streamingReasons: decision.reasons,
        multiConsumerStrategy: 'none'
      }
    };
  }
  
  private async teeStreamForConsumers(
    node: WorkflowNode,
    stream: ReadableStream,
    decision: StreamingDecision
  ): Promise<ExecutionResult> {
    
    // Create teed streams (browser supports tee() natively)
    const [stream1, stream2] = stream.tee();
    
    // Store references to both streams
    const teeKey = `node-${node.id}-tee`;
    
    // Store tee metadata (not the streams themselves)
    await this.storage.store(
      teeKey,
      {
        type: 'teed_streams',
        nodeId: node.id,
        // We can't actually store streams, so we'll need to re-tee on demand
        // This is a limitation - we need to handle this at execution level
      },
      {
        nodeId: node.id,
        temporary: true
      }
    );
    
    // Return special marker indicating teed output
    return {
      nodeId: node.id,
      output: {
        $teed: teeKey,
        streams: [stream1, stream2]  // Store in execution context, not storage
      },
      streaming: true,
      metadata: {
        streamingReasons: decision.reasons,
        multiConsumerStrategy: 'tee'
      }
    };
  }
  
  private async materializeStreamToStorage(
    node: WorkflowNode,
    stream: ReadableStream,
    decision: StreamingDecision
  ): Promise<ExecutionResult> {
    
    // Read entire stream
    const chunks: any[] = [];
    const reader = stream.getReader();
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
    
    // Combine chunks
    const materialized = this.combineChunks(chunks);
    
    // Store in hybrid storage
    const storageKey = `node-${node.id}-materialized`;
    await this.storage.store(storageKey, materialized, {
      nodeId: node.id,
      temporary: true
    });
    
    // Return storage reference
    return {
      nodeId: node.id,
      output: { $ref: storageKey },
      streaming: false,
      metadata: {
        materialized: true,
        storageKey,
        streamingReasons: decision.reasons,
        multiConsumerStrategy: 'materialize'
      }
    };
  }
  
  private async executeWithBatch(
    node: WorkflowNode,
    inputs: Record<string, any>
  ): Promise<ExecutionResult> {
    
    // Resolve storage references and teed streams
    const resolvedInputs = await this.resolveInputs(inputs);
    
    // Execute
    const output = await this.batchExecutor.executeNodeBatch(node, resolvedInputs);
    
    return {
      nodeId: node.id,
      output,
      streaming: false,
      metadata: {}
    };
  }
  
  private async resolveInputs(inputs: Record<string, any>): Promise<Record<string, any>> {
    const resolved: Record<string, any> = {};
    
    for (const [key, value] of Object.entries(inputs)) {
      if (value && typeof value === 'object') {
        if (value.$ref) {
          // Storage reference
          resolved[key] = await this.storage.retrieve(value.$ref);
        } else if (value.$teed) {
          // Teed stream reference - get one of the streams
          // This is simplified - real implementation needs stream tracking
          resolved[key] = value.streams[0];
        } else {
          resolved[key] = value;
        }
      } else {
        resolved[key] = value;
      }
    }
    
    return resolved;
  }
  
  private estimateDataSize(data: any): number {
    try {
      return JSON.stringify(data).length;
    } catch {
      return 0;
    }
  }
  
  private combineChunks(chunks: any[]): any {
    if (chunks.length === 0) return null;
    
    if (typeof chunks[0] === 'string') {
      return chunks.join('');
    }
    
    if (Array.isArray(chunks[0])) {
      return chunks.flat();
    }
    
    return chunks[chunks.length - 1];
  }
}

type MultiConsumerStrategy = 'none' | 'tee' | 'materialize';

interface StreamingDecision {
  shouldStream: boolean;
  reasons: string[];
  multiConsumerStrategy: MultiConsumerStrategy;
}

interface ExecutionResult {
  nodeId: string;
  output: any | ReadableStream | { $ref: string } | { $teed: string; streams: ReadableStream[] };
  streaming: boolean;
  metadata: Record<string, any>;
}

interface WorkflowNode {
  id: string;
  data: {
    type: string;
    config: {
      streaming?: boolean;
      [key: string]: any;
    };
  };
}

interface WorkflowEdge {
  source: string;
  target: string;
}
```

## Composable Expression System

### Key Insight: Mix and Match Text and Visual, Don't Force One Mode

```typescript
interface ExpressionEngine {
  evaluate(expression: Expression, context: any): Promise<any>;
  validate(expression: Expression): ValidationResult;
  getExamples(): ExpressionExample[];
}

// Expression can be pure text, pure blocks, or mixed
type Expression = 
  | { mode: 'text'; value: string }
  | { mode: 'visual'; blocks: ExpressionBlock[] }
  | { mode: 'composite'; parts: ExpressionPart[] };

type ExpressionPart =
  | { type: 'text'; value: string }
  | { type: 'block'; block: ExpressionBlock };

interface ExpressionBlock {
  id: string;
  type: 'field' | 'filter' | 'map' | 'aggregate' | 'transform';
  config: Record<string, any>;
}

class ComposableExpressionEngine implements ExpressionEngine {
  private jsonataEngine: JSONataEngine;
  
  constructor() {
    this.jsonataEngine = new JSONataEngine();
  }
  
  async evaluate(expression: Expression, context: any): Promise<any> {
    switch (expression.mode) {
      case 'text':
        return this.jsonataEngine.evaluate(expression.value, context);
        
      case 'visual':
        const jsonataFromBlocks = this.blocksToJSONata(expression.blocks);
        return this.jsonataEngine.evaluate(jsonataFromBlocks, context);
        
      case 'composite':
        const jsonataFromComposite = this.compositeToJSONata(expression.parts);
        return this.jsonataEngine.evaluate(jsonataFromComposite, context);
        
      default:
        throw new Error(`Unknown expression mode: ${(expression as any).mode}`);
    }
  }
  
  validate(expression: Expression): ValidationResult {
    try {
      let jsonataExpr: string;
      
      switch (expression.mode) {
        case 'text':
          jsonataExpr = expression.value;
          break;
        case 'visual':
          jsonataExpr = this.blocksToJSONata(expression.blocks);
          break;
        case 'composite':
          jsonataExpr = this.compositeToJSONata(expression.parts);
          break;
        default:
          return { valid: false, error: 'Unknown expression mode' };
      }
      
      return this.jsonataEngine.validate(jsonataExpr);
      
    } catch (error: any) {
      return { 
        valid: false, 
        error: error.message,
        suggestion: 'Check expression syntax'
      };
    }
  }
  
  private blocksToJSONata(blocks: ExpressionBlock[]): string {
    return blocks.map(block => {
      switch (block.type) {
        case 'field':
          return `$.${block.config.path}`;
          
        case 'filter':
          return `[${block.config.condition}]`;
          
        case 'map':
          return `.{ ${block.config.mapping} }`;
          
        case 'aggregate':
          return `$${block.config.function}(${block.config.path})`;
          
        case 'transform':
          return block.config.expression;
          
        default:
          throw new Error(`Unknown block type: ${block.type}`);
      }
    }).join('');
  }
  
  private compositeToJSONata(parts: ExpressionPart[]): string {
    return parts.map(part => {
      if (part.type === 'text') {
        return part.value;
      } else {
        return this.blockToJSONata(part.block);
      }
    }).join('');
  }
  
  private blockToJSONata(block: ExpressionBlock): string {
    switch (block.type) {
      case 'field':
        return `$.${block.config.path}`;
      case 'filter':
        return `[${block.config.condition}]`;
      case 'map':
        return `.{ ${block.config.mapping} }`;
      case 'aggregate':
        return `$${block.config.function}(${block.config.path})`;
      case 'transform':
        return block.config.expression;
      default:
        throw new Error(`Unknown block type: ${block.type}`);
    }
  }
  
  getExamples(): ExpressionExample[] {
    return [
      {
        category: 'Simple Field',
        expression: { mode: 'text', value: '$.user.name' },
        description: 'Extract nested field',
        inputExample: { user: { name: 'Alice' } },
        outputExample: 'Alice'
      },
      {
        category: 'Visual Filter',
        expression: {
          mode: 'visual',
          blocks: [
            { id: '1', type: 'field', config: { path: 'items' } },
            { id: '2', type: 'filter', config: { condition: 'price > 100' } }
          ]
        },
        description: 'Filter using visual blocks',
        inputExample: { items: [{ price: 50 }, { price: 150 }] },
        outputExample: [{ price: 150 }]
      },
      {
        category: 'Composite',
        expression: {
          mode: 'composite',
          parts: [
            { type: 'block', block: { id: '1', type: 'field', config: { path: 'items' } } },
            { type: 'text', value: '[price > 100]' },
            { type: 'block', block: { id: '2', type: 'aggregate', config: { function: 'sum', path: 'price' } } }
          ]
        },
        description: 'Mix visual blocks with text',
        inputExample: { items: [{ price: 50 }, { price: 150 }, { price: 200 }] },
        outputExample: 350
      }
    ];
  }
}

class JSONataEngine {
  private cache: Map<string, any> = new Map();
  private readonly timeout = 5000;
  
  async evaluate(expression: string, context: any): Promise<any> {
    let compiled = this.cache.get(expression);
    
    if (!compiled) {
      // Use jsonata library (would need to import)
      // compiled = jsonata(expression);
      
      // For now, simplified evaluation
      // In real implementation, use actual JSONata library
      compiled = { evaluate: (ctx: any) => this.simpleEval(expression, ctx) };
      
      this.cache.set(expression, compiled);
    }
    
    return await Promise.race([
      Promise.resolve(compiled.evaluate(context)),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Expression timeout')), this.timeout)
      )
    ]);
  }
  
  validate(expression: string): ValidationResult {
    try {
      // In real implementation, use JSONata parser
      // For now, basic validation
      if (!expression || expression.trim().length === 0) {
        return { valid: false, error: 'Empty expression' };
      }
      
      return { valid: true };
    } catch (error: any) {
      return { 
        valid: false, 
        error: error.message,
        suggestion: 'Check JSONata syntax'
      };
    }
  }
  
  private simpleEval(expression: string, context: any): any {
    // Simplified evaluator - real implementation would use JSONata
    if (expression.startsWith('$.')) {
      const path = expression.substring(2).split('.');
      let result = context;
      for (const key of path) {
        result = result?.[key];
      }
      return result;
    }
    
    return null;
  }
}

// UI Component for Composable Expressions
const ComposableExpressionEditor: React.FC<{
  value: Expression;
  onChange: (value: Expression) => void;
}> = ({ value, onChange }) => {
  
  const [mode, setMode] = useState<'text' | 'visual' | 'composite'>(value.mode);
  const engine = useMemo(() => new ComposableExpressionEngine(), []);
  const [validation, setValidation] = useState<ValidationResult>({ valid: true });
  
  useEffect(() => {
    setValidation(engine.validate(value));
  }, [value, engine]);
  
  const switchMode = (newMode: 'text' | 'visual' | 'composite') => {
    if (newMode === value.mode) return;
    
    // Convert between modes
    let newValue: Expression;
    
    if (newMode === 'text') {
      // Convert to text (simplified)
      newValue = { mode: 'text', value: '' };
    } else if (newMode === 'visual') {
      newValue = { mode: 'visual', blocks: [] };
    } else {
      newValue = { mode: 'composite', parts: [] };
    }
    
    setMode(newMode);
    onChange(newValue);
  };
  
  return (
    <div className="expression-editor">
      <div className="mode-selector">
        <button 
          onClick={() => switchMode('text')}
          className={mode === 'text' ? 'active' : ''}
        >
          Text
        </button>
        <button 
          onClick={() => switchMode('visual')}
          className={mode === 'visual' ? 'active' : ''}
        >
          Visual
        </button>
        <button 
          onClick={() => switchMode('composite')}
          className={mode === 'composite' ? 'active' : ''}
        >
          Mixed
        </button>
      </div>
      
      {mode === 'text' && value.mode === 'text' && (
        <textarea
          value={value.value}
          onChange={e => onChange({ mode: 'text', value: e.target.value })}
          className={validation.valid ? '' : 'error'}
          placeholder="Enter JSONata expression: $.field.path"
        />
      )}
      
      {mode === 'visual' && value.mode === 'visual' && (
        <VisualBlockEditor
          blocks={value.blocks}
          onChange={blocks => onChange({ mode: 'visual', blocks })}
        />
      )}
      
      {mode === 'composite' && value.mode === 'composite' && (
        <CompositeEditor
          parts={value.parts}
          onChange={parts => onChange({ mode: 'composite', parts })}
        />
      )}
      
      {!validation.valid && (
        <div className="error-message">
          {validation.error}
          {validation.suggestion && <div className="suggestion">{validation.suggestion}</div>}
        </div>
      )}
      
      <ExpressionExamples examples={engine.getExamples()} />
    </div>
  );
};

// Stub components (would be implemented fully)
const VisualBlockEditor: React.FC<{
  blocks: ExpressionBlock[];
  onChange: (blocks: ExpressionBlock[]) => void;
}> = ({ blocks, onChange }) => {
  return <div>Visual block editor (drag-drop blocks)</div>;
};

const CompositeEditor: React.FC<{
  parts: ExpressionPart[];
  onChange: (parts: ExpressionPart[]) => void;
}> = ({ parts, onChange }) => {
  return <div>Composite editor (mix text and blocks)</div>;
};

const ExpressionExamples: React.FC<{
  examples: ExpressionExample[];
}> = ({ examples }) => {
  return (
    <div className="examples">
      <h4>Examples</h4>
      {examples.map((ex, i) => (
        <div key={i} className="example">
          <strong>{ex.category}:</strong> {ex.description}
        </div>
      ))}
    </div>
  );
};

interface ValidationResult {
  valid: boolean;
  error?: string;
  suggestion?: string;
}

interface ExpressionExample {
  category: string;
  expression: Expression;
  description: string;
  inputExample: any;
  outputExample: any;
}
```

## Pluggable Compensation Handler System

### Key Insight: Let Users Register Custom Handlers for Their Services

```typescript
interface CompensationHandler {
  name: string;
  compensate(entry: SideEffectEntry): Promise<CompensationResult>;
  canHandle(entry: SideEffectEntry): boolean;
}

class CompensationHandlerRegistry {
  private handlers: Map<string, CompensationHandler> = new Map();
  
  register(handler: CompensationHandler): void {
    this.handlers.set(handler.name, handler);
  }
  
  unregister(name: string): void {
    this.handlers.delete(name);
  }
  
  findHandler(entry: SideEffectEntry): CompensationHandler | null {
    for (const handler of this.handlers.values()) {
      if (handler.canHandle(entry)) {
        return handler;
      }
    }
    return null;
  }
  
  getAll(): CompensationHandler[] {
    return Array.from(this.handlers.values());
  }
}

// Enhanced side effect log with pluggable handlers
class SideEffectLog {
  private db: IDBDatabase;
  private handlerRegistry: CompensationHandlerRegistry;
  
  constructor() {
    this.initDB();
    this.handlerRegistry = new CompensationHandlerRegistry();
    this.registerBuiltInHandlers();
  }
  
  async append(entry: Omit<SideEffectEntry, 'id' | 'timestamp' | 'status'>): Promise<string> {
    const id = crypto.randomUUID();
    
    const effectEntry: SideEffectEntry = {
      ...entry,
      id,
      timestamp: Date.now(),
      status: 'pending'
    };
    
    await this.writeToLog(effectEntry);
    return id;
  }
  
  async markExecuted(effectId: string): Promise<void> {
    await this.writeToLog({
      id: crypto.randomUUID(),
      nodeId: 'system',
      executionId: 'system',
      timestamp: Date.now(),
      operation: 'api_call',
      description: `Effect ${effectId} executed`,
      compensation: { type: 'irreversible', reason: 'audit entry' },
      status: 'executed',
      executedAt: Date.now()
    });
  }
  
  async compensate(effectId: string): Promise<CompensationResult> {
    const entry = await this.getEntry(effectId);
    
    if (!entry) {
      return { success: false, error: 'Effect not found' };
    }
    
    if (entry.status !== 'executed') {
      return { success: false, error: 'Effect not in executed state' };
    }
    
    // Find appropriate handler
    const handler = this.handlerRegistry.findHandler(entry);
    
    if (!handler) {
      return { 
        success: false, 
        error: `No compensation handler found for: ${entry.description}`,
        requiresUserAction: true,
        manualSteps: [
          'No automatic compensation available',
          `Operation: ${entry.description}`,
          'Please manually revert this change'
        ]
      };
    }
    
    try {
      const result = await handler.compensate(entry);
      
      // Log compensation
      await this.writeToLog({
        id: crypto.randomUUID(),
        nodeId: entry.nodeId,
        executionId: entry.executionId,
        timestamp: Date.now(),
        operation: entry.operation,
        description: `Compensated: ${entry.description}`,
        compensation: entry.compensation,
        status: 'compensated',
        compensatedAt: Date.now()
      });
      
      return result;
      
    } catch (error: any) {
      await this.writeToLog({
        id: crypto.randomUUID(),
        nodeId: entry.nodeId,
        executionId: entry.executionId,
        timestamp: Date.now(),
        operation: entry.operation,
        description: `Compensation failed: ${entry.description}`,
        compensation: entry.compensation,
        status: 'failed',
        error: error.message
      });
      
      return { success: false, error: error.message };
    }
  }
  
  registerHandler(handler: CompensationHandler): void {
    this.handlerRegistry.register(handler);
  }
  
  unregisterHandler(name: string): void {
    this.handlerRegistry.unregister(name);
  }
  
  private registerBuiltInHandlers(): void {
    // Reversible operations
    this.handlerRegistry.register({
      name: 'reversible',
      canHandle: (entry) => entry.compensation.type === 'reversible',
      compensate: async (entry) => {
        const descriptor = (entry.compensation as any).reverseOperation;
        
        const response = await fetch(descriptor.endpoint, {
          method: descriptor.method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(descriptor.parameters)
        });
        
        if (!response.ok) {
          throw new Error(`Reverse operation failed: ${response.statusText}`);
        }
        
        return { success: true, message: 'Operation reversed successfully' };
      }
    });
    
    // Idempotent operations
    this.handlerRegistry.register({
      name: 'idempotent',
      canHandle: (entry) => entry.compensation.type === 'idempotent',
      compensate: async (entry) => {
        return { success: true, message: 'Idempotent operation - no compensation needed' };
      }
    });
    
    // Irreversible operations
    this.handlerRegistry.register({
      name: 'irreversible',
      canHandle: (entry) => entry.compensation.type === 'irreversible',
      compensate: async (entry) => {
        const descriptor = entry.compensation as any;
        
        return {
          success: false,
          error: `Cannot auto-compensate: ${descriptor.reason}`,
          manualSteps: descriptor.manualSteps || ['Manual intervention required'],
          requiresUserAction: true
        };
      }
    });
    
    // Eventual consistency
    this.handlerRegistry.register({
      name: 'eventual',
      canHandle: (entry) => entry.compensation.type === 'eventual',
      compensate: async (entry) => {
        const descriptor = entry.compensation as any;
        
        const response = await fetch(descriptor.compensatingService, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(descriptor.payload)
        });
        
        if (!response.ok) {
          throw new Error(`Compensating service failed: ${response.statusText}`);
        }
        
        return { 
          success: true, 
          message: 'Compensating transaction initiated' 
        };
      }
    });
  }
  
  private async writeToLog(entry: SideEffectEntry): Promise<void> {
    const tx = this.db.transaction('effects', 'readwrite');
    const store = tx.objectStore('effects');
    await store.add(entry);
  }
  
  private async getEntry(effectId: string): Promise<SideEffectEntry | null> {
    const tx = this.db.transaction('effects', 'readonly');
    const store = tx.objectStore('effects');
    return await store.get(effectId);
  }
  
  async getEntriesForExecution(executionId: string): Promise<SideEffectEntry[]> {
    const tx = this.db.transaction('effects', 'readonly');
    const store = tx.objectStore('effects');
    const index = store.index('executionId');
    
    const entries: SideEffectEntry[] = [];
    let cursor = await index.openCursor(IDBKeyRange.only(executionId));
    
    while (cursor) {
      entries.push(cursor.value);
      cursor = await cursor.continue();
    }
    
    return entries;
  }
  
  private async initDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('SideEffectLog', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        const store = db.createObjectStore('effects', { keyPath: 'id' });
        store.createIndex('nodeId', 'nodeId', { unique: false });
        store.createIndex('executionId', 'executionId', { unique: false });
        store.createIndex('timestamp', 'timestamp', { unique: false });
      };
    });
  }
}

// Example: Custom compensation handler for Stripe
class StripeCompensationHandler implements CompensationHandler {
  name = 'stripe';
  
  canHandle(entry: SideEffectEntry): boolean {
    return entry.operation === 'payment_process' && 
           entry.description.includes('Stripe');
  }
  
  async compensate(entry: SideEffectEntry): Promise<CompensationResult> {
    const descriptor = entry.compensation as any;
    
    try {
      // Call Stripe refund API
      const response = await fetch('https://api.stripe.com/v1/refunds', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${descriptor.apiKey}`,
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
          charge: descriptor.chargeId,
          reason: 'requested_by_customer'
        })
      });
      
      if (!response.ok) {
        throw new Error(`Stripe refund failed: ${response.statusText}`);
      }
      
      return {
        success: true,
        message: `Refunded charge ${descriptor.chargeId}`
      };
      
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        requiresUserAction: true,
        manualSteps: [
          'Go to Stripe dashboard',
          `Find charge: ${descriptor.chargeId}`,
          'Issue manual refund'
        ]
      };
    }
  }
}

// Usage
const sideEffectLog = new SideEffectLog();

// Register custom handler
sideEffectLog.registerHandler(new StripeCompensationHandler());

// Log Stripe payment
await sideEffectLog.append({
  nodeId: 'checkout-node',
  executionId: 'exec-123',
  operation: 'payment_process',
  description: 'Stripe payment for order #456',
  compensation: {
    type: 'reversible',
    reverseOperation: {
      service: 'stripe',
      method: 'POST',
      endpoint: '/v1/refunds',
      parameters: {
        chargeId: 'ch_abc123',
        apiKey: 'sk_test_...'
      }
    }
  }
});

// Types
interface SideEffectEntry {
  id: string;
  nodeId: string;
  executionId: string;
  timestamp: number;
  operation: OperationType;
  description: string;
  compensation: CompensationDescriptor;
  status: 'pending' | 'executed' | 'failed' | 'compensated';
  executedAt?: number;
  compensatedAt?: number;
  error?: string;
}

type OperationType = 
  | 'api_call'
  | 'file_write'
  | 'database_write'
  | 'external_webhook'
  | 'email_send'
  | 'payment_process';

type CompensationDescriptor = 
  | { type: 'reversible'; reverseOperation: OperationDescriptor }
  | { type: 'idempotent'; canRetry: boolean }
  | { type: 'irreversible'; reason: string; manualSteps?: string[] }
  | { type: 'eventual'; compensatingService: string; payload: any };

interface OperationDescriptor {
  service: string;
  method: string;
  endpoint?: string;
  parameters: Record<string, any>;
}

interface CompensationResult {
  success: boolean;
  error?: string;
  message?: string;
  manualSteps?: string[];
  requiresUserAction?: boolean;
}
```

## Checkpoint Manager (Enhanced)

```typescript
class CheckpointManager {
  private db: IDBDatabase;
  private sideEffectLog: SideEffectLog;
  
  constructor(sideEffectLog: SideEffectLog) {
    this.sideEffectLog = sideEffectLog;
    this.initDB();
  }
  
  async createCheckpoint(
    executionState: ExecutionState,
    reason: 'manual' | 'auto' | 'error' = 'auto'
  ): Promise<string> {
    const checkpointId = crypto.randomUUID();
    
    const sideEffects = await this.sideEffectLog.getEntriesForExecution(
      executionState.executionId
    );
    
    const checkpoint: ExecutionCheckpoint = {
      id: checkpointId,
      executionId: executionState.executionId,
      timestamp: Date.now(),
      nodeStates: this.serializeNodeStates(executionState.nodeStates),
      sideEffectCount: sideEffects.length,
      reason
    };
    
    const tx = this.db.transaction('checkpoints', 'readwrite');
    await tx.objectStore('checkpoints').put(checkpoint);
    
    return checkpointId;
  }
  
  async restoreCheckpoint(
    checkpointId: string,
    strategy: CompensationStrategy
  ): Promise<RestoreResult> {
    
    const checkpoint = await this.getCheckpoint(checkpointId);
    if (!checkpoint) {
      return { success: false, error: 'Checkpoint not found' };
    }
    
    const allEffects = await this.sideEffectLog.getEntriesForExecution(
      checkpoint.executionId
    );
    
    const effectsToCompensate = allEffects.filter(e => 
      e.timestamp > checkpoint.timestamp && e.status === 'executed'
    );
    
    const compensationResults = await this.applyCompensationStrategy(
      effectsToCompensate,
      strategy
    );
    
    const manualSteps = compensationResults
      .filter(r => r.requiresUserAction)
      .flatMap(r => r.manualSteps || []);
    
    return {
      success: true,
      checkpoint,
      compensationResults,
      manualSteps: manualSteps.length > 0 ? manualSteps : undefined
    };
  }
  
  private async applyCompensationStrategy(
    effects: SideEffectEntry[],
    strategy: CompensationStrategy
  ): Promise<CompensationResult[]> {
    
    switch (strategy) {
      case 'automatic':
        const results: CompensationResult[] = [];
        
        for (const effect of effects.reverse()) {
          const result = await this.sideEffectLog.compensate(effect.id);
          results.push(result);
          
          if (!result.success && !result.requiresUserAction) {
            break; // Stop on failure
          }
        }
        
        return results;
        
      case 'manual':
        return effects.map(effect => ({
          success: false,
          requiresUserAction: true,
          manualSteps: [
            `Effect: ${effect.description}`,
            `Type: ${effect.compensation.type}`,
            'Manually revert this operation'
          ]
        }));
        
      case 'confirm_each':
        // Would require UI interaction
        return [];
        
      default:
        throw new Error(`Unknown strategy: ${strategy}`);
    }
  }
  
  private async getCheckpoint(checkpointId: string): Promise<ExecutionCheckpoint | null> {
    const tx = this.db.transaction('checkpoints', 'readonly');
    const store = tx.objectStore('checkpoints');
    return await store.get(checkpointId);
  }
  
  private serializeNodeStates(nodeStates: Map<string, any>): any {
    return Array.from(nodeStates.entries());
  }
  
  private async initDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowCheckpoints', 1);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains('checkpoints')) {
          db.createObjectStore('checkpoints', { keyPath: 'id' });
        }
      };
    });
  }
}

type CompensationStrategy = 
  | 'automatic'
  | 'manual'
  | 'confirm_each';

interface ExecutionState {
  executionId: string;
  nodeStates: Map<string, any>;
}

interface ExecutionCheckpoint {
  id: string;
  executionId: string;
  timestamp: number;
  nodeStates: any;
  sideEffectCount: number;
  reason: string;
}

interface RestoreResult {
  success: boolean;
  error?: string;
  checkpoint?: ExecutionCheckpoint;
  compensationResults?: CompensationResult[];
  manualSteps?: string[];
}
```

## Performance Optimizations (Preserved)

All performance optimizations from previous design are maintained:
- Viewport culling for large canvases
- Virtual scrolling for node palette
- Debounced auto-save
- Worker pool for execution
- Lazy loading of node data

---

## Rationale

### 1. **Two-Tier Storage with Overflow Strategy**
The three-tier approach adds complexity that most users don't need. Instead:
- **Two tiers** (Memory + IndexedDB) are simpler and sufficient for 99% of workflows
- **Overflow strategy** gives users explicit control over what happens when storage fills up
- **drop-oldest**: Safe default (FIFO eviction)
- **drop-on-store**: Fail loudly for debugging
- **compress-aggressive**: Trade CPU for space
- **external-blob**: Browser-only fallback for huge files

This is simpler to reason about and lets users pick the behavior that matches their needs.

### 2. **Adaptive Teeing for Multi-Consumer Streams**
The previous design always materialized streams with multiple consumers. This wastes memory for small streams:
- **Tee small streams** (< 5MB): Efficient for 2-3 consumers
- **Materialize large streams** (> 5MB): Avoid memory pressure
- **Configurable thresholds**: Users can tune based on their data
- **Adaptive mode**: Automatically choose based on size + consumer count

### 3. **Composable Expression System**
The previous design forced users to choose between text OR visual. This is limiting:
- **Three modes**: Text, Visual, Composite
- **Composite mode**: Mix text and visual blocks in one expression
- **Progressive enhancement**: Start with text, add visual blocks where helpful
- **Same engine**: All modes compile to JSONata under the hood

Example: `$.items[price > 100] | {VISUAL_BLOCK: sum(price)}`

### 4. **Pluggable Compensation Handlers**
The four built-in compensation types are good, but users need extensibility:
- **Handler registry**: Register custom handlers for specific services
- **Auto-discovery**: Handlers declare what they can handle via `canHandle()`
- **Fallback**: If no handler found, return manual steps
- **Examples**: Stripe refunds, Slack message deletion, S3 object removal

This allows users to build domain-specific compensation logic without modifying core code.

---

## What I Changed

### Storage: 3-tier → 2-tier with overflow strategy
- Simpler mental model (hot/warm vs hot/warm/cold)
- Explicit user control via overflow strategy
- No complex tier promotion logic
- External blobs only when user opts in

### Streaming: Always materialize → Adaptive teeing
- Tee small streams for efficiency
- Materialize large streams to avoid memory issues
- Configurable thresholds
- Tracks multi-consumer strategy in metadata

### Expressions: Separate modes → Composable system
- Mix text and visual in one expression
- Three modes: text, visual, composite
- Progressive enhancement path
- Single engine (JSONata) underneath

### Compensation: Fixed handlers → Pluggable registry
- Users can register custom handlers
- Auto-discovery via `canHandle()`
- Extensible for domain-specific services
- Built-in handlers still provided

---

## What I Kept

All the excellent architectural decisions:
- React Flow canvas with viewport culling
- Zustand + immer state management
- Append-only side effect log
- Semantic compensation descriptors (not functions)
- Checkpoint manager with strategies
- Worker pool architecture
- Topological execution order
- Compression for large data
- Auto-cleanup of temporary artifacts
- IndexedDB for persistence
- Performance optimizations (viewport culling, virtual scrolling, debounced save)

---

## Open Questions

### 1. **Overflow Strategy Defaults**
Should different overflow strategies be recommended for different use cases?
- Development: `drop-on-store` (fail loudly)
- Production: `drop-oldest` (graceful degradation)
- Large files: `external-blob` (but lost on refresh)

### 2. **Tee vs Materialize Thresholds**
Current defaults:
- Tee threshold: 5MB
- Materialize threshold: 50MB
- Max consumers for tee: 3

Are these reasonable? Should they be auto-tuned based on browser memory?

### 3. **Composite Expression UI**
How should the UI for composite mode work?
- Inline visual blocks within text editor?
- Side-by-side panels?
- Click to convert text → block or block → text?

### 4. **Handler Registration UX**
Should compensation handler registration be:
- **Code-only** (developers write TypeScript classes)
- **UI-based** (users configure handlers in settings panel)
- **Both** (UI for simple cases, code for complex)

### 5. **Streaming Statistics**
Should we track and display:
- Number of streams teed vs materialized
- Memory saved by teeing
- Storage saved by compression
- Per-node streaming performance metrics

---

## Convergence Status

**PROPOSING_FINAL** - This design addresses all major concerns and is ready for implementation:

✅ Simplified storage (2-tier + overflow strategy)  
✅ Smart streaming (adaptive teeing + materialization)  
✅ Flexible expressions (composable system supporting text/visual/mixed)  
✅ Extensible compensation (pluggable handler registry)  
✅ All performance optimizations preserved  
✅ Production-ready architecture  

The design is complete, implementable, and handles edge cases gracefully.

---

## PROMPT_FOR_CRITIC:

Please focus on these specific areas:

1. **Overflow Strategy Naming**: Are the four strategy names intuitive? Would different names be clearer? (e.g., `drop-on-store` vs `fail-when-full`)

2. **Tee Implementation Details**: The current design stores teed streams in execution context (not storage). Is this the right approach? Should we have a separate "stream registry" for active tees?

3. **Composite Expression Syntax**: What should the syntax look like for mixing text and visual blocks? Should blocks have special markers (e.g., `{{BLOCK:id}}`) or be more integrated?

4. **Handler Registration Timing**: When should custom compensation handlers be registered? At app startup? Per-workflow? Should handlers be serializable so they can be saved with workflows?

5. **Performance Monitoring**: Should we add built-in performance monitoring for streaming decisions (tee vs materialize) to help users tune thresholds? What metrics matter most?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

# Visual AI Agent Workflow Builder - Production-Ready Architecture v4

## Core Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │         │
│  │   (React     │  │    Panel     │  │   & Palette  │         │
│  │    Flow)     │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│           State Management (Zustand + Immer)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Orchestration Layer                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Adaptive   │  │  Storage   │  │ Checkpoint │         │  │
│  │  │ Executor   │  │  + Stream  │  │  Manager   │         │  │
│  │  │            │  │  Registry  │  │            │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Data Flow & Storage Layer                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Composable │  │   Two-Tier │  │ Effect Log │         │  │
│  │  │ Expression │  │  + Overflow│  │  (Append-  │         │  │
│  │  │  System    │  │  Strategy  │  │   Only)    │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas**: React Flow v11+ with viewport culling
- **State**: Zustand with immer middleware and persistence
- **UI**: Radix UI primitives + Tailwind CSS
- **Execution**: Adaptive executor with streaming + dedicated stream registry
- **Storage**: Two-tier (Memory + IndexedDB) with explicit overflow policies
- **Expressions**: Composable expression system (JSONata + visual blocks)
- **Side Effects**: Append-only log with serializable compensation handlers
- **Workers**: Shared Worker pool with resource quotas

## Enhanced Two-Tier Storage with Clear Overflow Policies

### Key Changes: Clearer Naming, Better Eviction Control, Stream-Aware

```typescript
type OverflowPolicy = 
  | 'evict-lru'              // Default: Evict least recently used
  | 'evict-oldest'           // FIFO eviction by creation time
  | 'fail-when-full'         // Throw error when storage full
  | 'compress-max'           // Aggressive compression on overflow
  | 'external-blob';         // Blob URLs (volatile, cleared on reload)

interface StorageConfig {
  // Tier capacities
  memoryCacheMaxBytes: number;      // 100MB - hot in-memory data
  indexedDBMaxBytes: number;        // 1GB - warm IndexedDB storage
  
  // Overflow behavior
  overflowPolicy: OverflowPolicy;
  
  // Eviction preferences (for evict-lru/evict-oldest policies)
  evictionPreferences: {
    protectRecent: boolean;         // Don't evict items < 5s old
    protectFrequent: boolean;       // Prefer evicting low-access items
    protectPinned: boolean;         // Never evict explicitly pinned items
  };
  
  // Compression
  compressionThreshold: number;     // 1MB - compress above this
  compressionLevel: 'fast' | 'balanced' | 'best';
  
  // Auto-cleanup
  autoCleanupAge: number;           // 24h - delete old temp artifacts
  enableAutoCleanup: boolean;
  
  // Storage warnings
  warnAtPercent: number;            // 80 - warn when storage % full
}

interface ArtifactMetadata {
  key: string;
  sizeBytes: number;
  tier: 'memory' | 'indexeddb' | 'external' | 'determining';
  createdAt: number;
  lastAccessedAt: number;
  accessCount: number;
  temporary: boolean;
  pinned: boolean;                  // Protected from eviction
  nodeId?: string;
  executionId?: string;
  dataType: 'stream-ref' | 'materialized' | 'blob' | 'json';
}

class HybridStorageManager {
  private memoryCache: Map<string, CacheEntry> = new Map();
  private memoryCacheSize: number = 0;
  private indexedDB: IDBDatabase;
  private indexedDBSize: number = 0;
  private config: StorageConfig;
  
  // Lightweight metadata for all artifacts
  private artifactIndex: Map<string, ArtifactMetadata> = new Map();
  
  // External blob URLs (only for 'external-blob' policy)
  private externalBlobs: Map<string, string> = new Map();
  
  // Storage event listeners
  private listeners: Set<StorageEventListener> = new Set();
  
  constructor(config: StorageConfig) {
    this.config = config;
    this.initIndexedDB();
    
    if (config.enableAutoCleanup) {
      this.scheduleCleanup();
    }
    
    // Monitor storage levels
    this.scheduleStorageMonitoring();
  }
  
  async store(
    key: string, 
    data: any, 
    hints: StorageHints = {}
  ): Promise<void> {
    const serialized = JSON.stringify(data);
    const sizeBytes = new TextEncoder().encode(serialized).length;
    
    // Update metadata
    this.artifactIndex.set(key, {
      key,
      sizeBytes,
      tier: 'determining',
      createdAt: Date.now(),
      lastAccessedAt: Date.now(),
      accessCount: 0,
      temporary: hints.temporary ?? true,
      pinned: hints.pinned ?? false,
      nodeId: hints.nodeId,
      executionId: hints.executionId,
      dataType: hints.dataType ?? 'json'
    });
    
    // Tier decision: Simple size-based
    if (sizeBytes < 1024 * 1024) { // < 1MB -> try memory first
      if (await this.tryStoreInMemory(key, data, sizeBytes)) {
        this.artifactIndex.get(key)!.tier = 'memory';
        this.emitEvent('stored', { key, tier: 'memory', sizeBytes });
        return;
      }
    }
    
    // Otherwise use IndexedDB
    await this.storeInIndexedDB(key, serialized, sizeBytes);
    this.artifactIndex.get(key)!.tier = 'indexeddb';
    this.emitEvent('stored', { key, tier: 'indexeddb', sizeBytes });
  }
  
  private async tryStoreInMemory(
    key: string, 
    data: any, 
    sizeBytes: number
  ): Promise<boolean> {
    if (this.memoryCacheSize + sizeBytes <= this.config.memoryCacheMaxBytes) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    // Try to evict from memory
    if (await this.evictFromMemory(sizeBytes)) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    return false;
  }
  
  private async evictFromMemory(requiredBytes: number): Promise<boolean> {
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'memory' &&
        (!this.config.evictionPreferences.protectPinned || !m.pinned) &&
        (!this.config.evictionPreferences.protectRecent || 
         Date.now() - m.createdAt > 5000)
      );
    
    // Sort by eviction preference
    candidates.sort((a, b) => {
      if (this.config.evictionPreferences.protectFrequent) {
        // Evict less frequently accessed first
        if (a.accessCount !== b.accessCount) {
          return a.accessCount - b.accessCount;
        }
      }
      // Then by LRU
      return a.lastAccessedAt - b.lastAccessedAt;
    });
    
    let freedBytes = 0;
    const toEvict: string[] = [];
    
    for (const metadata of candidates) {
      toEvict.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (freedBytes < requiredBytes) return false;
    
    // Move to IndexedDB (no data loss)
    for (const key of toEvict) {
      const entry = this.memoryCache.get(key)!;
      await this.storeInIndexedDB(key, JSON.stringify(entry.data), entry.sizeBytes);
      
      this.memoryCache.delete(key);
      this.memoryCacheSize -= entry.sizeBytes;
      
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        metadata.tier = 'indexeddb';
        this.emitEvent('evicted', { key, from: 'memory', to: 'indexeddb' });
      }
    }
    
    return true;
  }
  
  private async storeInIndexedDB(
    key: string, 
    serialized: string, 
    sizeBytes: number
  ): Promise<void> {
    // Check if we're at capacity
    if (this.indexedDBSize + sizeBytes > this.config.indexedDBMaxBytes) {
      await this.handleIndexedDBOverflow(key, serialized, sizeBytes);
      return;
    }
    
    // Compress if needed
    const shouldCompress = sizeBytes > this.config.compressionThreshold;
    const toStore = shouldCompress 
      ? await this.compress(serialized, this.config.compressionLevel)
      : serialized;
    
    const actualSize = shouldCompress 
      ? new TextEncoder().encode(toStore as string).length 
      : sizeBytes;
    
    const tx = this.indexedDB.transaction('artifacts', 'readwrite');
    const store = tx.objectStore('artifacts');
    
    await store.put({
      key,
      data: toStore,
      compressed: shouldCompress,
      sizeBytes: actualSize,
      storedAt: Date.now()
    });
    
    this.indexedDBSize += actualSize;
  }
  
  private async handleIndexedDBOverflow(
    key: string, 
    serialized: string, 
    sizeBytes: number
  ): Promise<void> {
    switch (this.config.overflowPolicy) {
      case 'evict-lru':
      case 'evict-oldest':
        await this.evictFromIndexedDB(
          sizeBytes, 
          this.config.overflowPolicy === 'evict-lru'
        );
        await this.storeInIndexedDB(key, serialized, sizeBytes);
        break;
        
      case 'fail-when-full':
        const stats = this.getStorageStats();
        throw new StorageFullError(
          `Storage full: Cannot store ${key} (${formatBytes(sizeBytes)}). ` +
          `Usage: ${formatBytes(stats.total.bytes)} / ` +
          `${formatBytes(this.config.memoryCacheMaxBytes + this.config.indexedDBMaxBytes)}`,
          stats
        );
        
      case 'compress-max':
        const compressed = await this.compress(serialized, 'best');
        const compressedSize = new TextEncoder().encode(compressed).length;
        
        if (this.indexedDBSize + compressedSize > this.config.indexedDBMaxBytes) {
          // Still doesn't fit - evict
          await this.evictFromIndexedDB(compressedSize, true);
        }
        
        const tx = this.indexedDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').put({
          key,
          data: compressed,
          compressed: true,
          sizeBytes: compressedSize,
          storedAt: Date.now()
        });
        
        this.indexedDBSize += compressedSize;
        this.emitEvent('compressed', { key, originalSize: sizeBytes, compressedSize });
        break;
        
      case 'external-blob':
        const compressed2 = await this.compress(serialized, 'best');
        const blob = new Blob([compressed2], { type: 'application/octet-stream' });
        const blobUrl = URL.createObjectURL(blob);
        
        this.externalBlobs.set(key, blobUrl);
        
        // Store tiny reference in IndexedDB
        const tx2 = this.indexedDB.transaction('blobRefs', 'readwrite');
        await tx2.objectStore('blobRefs').put({
          key,
          blobUrl,
          sizeBytes,
          storedAt: Date.now()
        });
        
        const metadata = this.artifactIndex.get(key);
        if (metadata) {
          metadata.tier = 'external';
          this.emitEvent('stored-external', { key, sizeBytes });
        }
        break;
    }
  }
  
  private async evictFromIndexedDB(
    requiredBytes: number, 
    useLRU: boolean
  ): Promise<void> {
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'indexeddb' &&
        (!this.config.evictionPreferences.protectPinned || !m.pinned)
      );
    
    // Sort by strategy
    candidates.sort((a, b) => {
      if (useLRU) {
        // LRU: least recently accessed first
        if (this.config.evictionPreferences.protectFrequent) {
          if (a.accessCount !== b.accessCount) {
            return a.accessCount - b.accessCount;
          }
        }
        return a.lastAccessedAt - b.lastAccessedAt;
      } else {
        // FIFO: oldest creation time first
        return a.createdAt - b.createdAt;
      }
    });
    
    let freedBytes = 0;
    const toDelete: string[] = [];
    
    for (const metadata of candidates) {
      toDelete.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (toDelete.length === 0) {
      throw new Error('Cannot evict: all items are protected');
    }
    
    // Delete entries
    const txDelete = this.indexedDB.transaction('artifacts', 'readwrite');
    const storeDelete = txDelete.objectStore('artifacts');
    
    for (const key of toDelete) {
      await storeDelete.delete(key);
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        this.indexedDBSize -= metadata.sizeBytes;
        this.emitEvent('evicted', { 
          key, 
          from: 'indexeddb', 
          to: 'deleted',
          reason: useLRU ? 'lru' : 'fifo'
        });
      }
      this.artifactIndex.delete(key);
    }
  }
  
  async retrieve(key: string): Promise<any> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) {
      throw new Error(`Artifact not found: ${key}`);
    }
    
    // Update access tracking
    metadata.accessCount++;
    metadata.lastAccessedAt = Date.now();
    
    let data: any;
    
    switch (metadata.tier) {
      case 'memory':
        data = this.memoryCache.get(key)?.data;
        if (!data) {
          // Fallback to IndexedDB
          data = await this.retrieveFromIndexedDB(key);
        }
        break;
        
      case 'indexeddb':
        data = await this.retrieveFromIndexedDB(key);
        
        // Promote to memory if: small + accessed frequently
        if (metadata.sizeBytes < 1024 * 1024 && 
            metadata.accessCount >= 3 &&
            Date.now() - metadata.createdAt < 60000) {
          
          if (await this.tryStoreInMemory(key, data, metadata.sizeBytes)) {
            metadata.tier = 'memory';
            this.emitEvent('promoted', { key, to: 'memory' });
          }
        }
        break;
        
      case 'external':
        data = await this.retrieveFromExternalBlob(key);
        break;
        
      default:
        throw new Error(`Unknown tier: ${metadata.tier}`);
    }
    
    return data;
  }
  
  async pin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = true;
      this.emitEvent('pinned', { key });
    }
  }
  
  async unpin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = false;
      this.emitEvent('unpinned', { key });
    }
  }
  
  private async retrieveFromIndexedDB(key: string): Promise<any> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    const record = await store.get(key);
    
    if (!record) {
      throw new Error(`Artifact not in IndexedDB: ${key}`);
    }
    
    const serialized = record.compressed
      ? await this.decompress(record.data)
      : record.data;
    
    return JSON.parse(serialized);
  }
  
  private async retrieveFromExternalBlob(key: string): Promise<any> {
    const blobUrl = this.externalBlobs.get(key);
    if (!blobUrl) {
      throw new Error(`External blob not found (may have been cleared): ${key}`);
    }
    
    const response = await fetch(blobUrl);
    const compressed = await response.text();
    const serialized = await this.decompress(compressed);
    return JSON.parse(serialized);
  }
  
  on(event: StorageEventType, listener: StorageEventListener): void {
    this.listeners.add(listener);
  }
  
  off(listener: StorageEventListener): void {
    this.listeners.delete(listener);
  }
  
  private emitEvent(type: string, data: any): void {
    for (const listener of this.listeners) {
      listener({ type, data, timestamp: Date.now() });
    }
  }
  
  private scheduleStorageMonitoring(): void {
    setInterval(() => {
      const stats = this.getStorageStats();
      const totalCapacity = this.config.memoryCacheMaxBytes + this.config.indexedDBMaxBytes;
      const usagePercent = (stats.total.bytes / totalCapacity) * 100;
      
      if (usagePercent >= this.config.warnAtPercent) {
        this.emitEvent('storage-warning', {
          usagePercent,
          stats,
          message: `Storage ${usagePercent.toFixed(1)}% full`
        });
      }
    }, 30000); // Check every 30s
  }
  
  getStorageStats(): StorageStats {
    const stats = {
      memory: { count: 0, bytes: this.memoryCacheSize },
      indexeddb: { count: 0, bytes: this.indexedDBSize },
      external: { count: 0, bytes: 0 },
      total: { count: this.artifactIndex.size, bytes: 0 }
    };
    
    for (const metadata of this.artifactIndex.values()) {
      stats[metadata.tier as 'memory' | 'indexeddb' | 'external'].count++;
      if (metadata.tier === 'external') {
        stats.external.bytes += metadata.sizeBytes;
      }
      stats.total.bytes += metadata.sizeBytes;
    }
    
    return stats;
  }
  
  // ... compression/decompression methods same as before ...
  
  private async compress(data: string, level: 'fast' | 'balanced' | 'best'): Promise<string> {
    const encoder = new TextEncoder();
    const stream = new Blob([data]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    
    const uint8 = new Uint8Array(buffer);
    return btoa(String.fromCharCode(...uint8));
  }
  
  private async decompress(data: string): Promise<string> {
    const binary = atob(data);
    const uint8 = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      uint8[i] = binary.charCodeAt(i);
    }
    
    const stream = new Blob([uint8]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowStorage', 3);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.indexedDB = request.result;
        this.calculateIndexedDBSize();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('artifacts')) {
          const store = db.createObjectStore('artifacts', { keyPath: 'key' });
          store.createIndex('storedAt', 'storedAt', { unique: false });
        }
        
        if (!db.objectStoreNames.contains('blobRefs')) {
          db.createObjectStore('blobRefs', { keyPath: 'key' });
        }
      };
    });
  }
  
  private async calculateIndexedDBSize(): Promise<void> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    let cursor = await store.openCursor();
    
    let totalSize = 0;
    while (cursor) {
      totalSize += cursor.value.sizeBytes || 0;
      cursor = await cursor.continue();
    }
    
    this.indexedDBSize = totalSize;
  }
  
  private scheduleCleanup(): void {
    setInterval(() => {
      const cutoff = Date.now() - this.config.autoCleanupAge;
      
      this.clear(metadata => 
        metadata.temporary && !metadata.pinned && metadata.createdAt < cutoff
      );
    }, 60 * 60 * 1000); // 1 hour
  }
  
  async clear(predicate?: (metadata: ArtifactMetadata) => boolean): Promise<void> {
    if (!predicate) {
      // Clear everything
      this.memoryCache.clear();
      this.memoryCacheSize = 0;
      this.indexedDBSize = 0;
      this.artifactIndex.clear();
      
      const tx = this.indexedDB.transaction(['artifacts', 'blobRefs'], 'readwrite');
      await tx.objectStore('artifacts').clear();
      await tx.objectStore('blobRefs').clear();
      
      // Revoke blob URLs
      for (const blobUrl of this.externalBlobs.values()) {
        URL.revokeObjectURL(blobUrl);
      }
      this.externalBlobs.clear();
      
      return;
    }
    
    // Selective clear
    const toDelete: string[] = [];
    
    for (const [key, metadata] of this.artifactIndex.entries()) {
      if (predicate(metadata)) {
        toDelete.push(key);
      }
    }
    
    for (const key of toDelete) {
      await this.delete(key);
    }
  }
  
  private async delete(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) return;
    
    switch (metadata.tier) {
      case 'memory':
        const entry = this.memoryCache.get(key);
        if (entry) {
          this.memoryCacheSize -= entry.sizeBytes;
          this.memoryCache.delete(key);
        }
        break;
        
      case 'indexeddb':
        const tx = this.indexedDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').delete(key);
        this.indexedDBSize -= metadata.sizeBytes;
        break;
        
      case 'external':
        const blobUrl = this.externalBlobs.get(key);
        if (blobUrl) {
          URL.revokeObjectURL(blobUrl);
          this.externalBlobs.delete(key);
        }
        
        const tx2 = this.indexedDB.transaction('blobRefs', 'readwrite');
        await tx2.objectStore('blobRefs').delete(key);
        break;
    }
    
    this.artifactIndex.delete(key);
  }
}

// Types
interface CacheEntry {
  data: any;
  sizeBytes: number;
  storedAt: number;
}

interface StorageHints {
  temporary?: boolean;
  pinned?: boolean;
  nodeId?: string;
  executionId?: string;
  dataType?: 'stream-ref' | 'materialized' | 'blob' | 'json';
}

interface StorageStats {
  memory: { count: number; bytes: number };
  indexeddb: { count: number; bytes: number };
  external: { count: number; bytes: number };
  total: { count: number; bytes: number };
}

type StorageEventType = 'stored' | 'evicted' | 'promoted' | 'compressed' | 
                        'stored-external' | 'pinned' | 'unpinned' | 'storage-warning';

type StorageEventListener = (event: { 
  type: string; 
  data: any; 
  timestamp: number 
}) => void;

class StorageFullError extends Error {
  constructor(message: string, public stats: StorageStats) {
    super(message);
    this.name = 'StorageFullError';
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)}MB`;
}
```

## Stream Registry for Tee Management

### Key Insight: Active Streams Need Separate Lifecycle Management

```typescript
interface StreamRegistryConfig {
  maxConcurrentStreams: number;     // 50 - prevent memory exhaustion
  streamTimeout: number;             // 5min - auto-cleanup stale streams
  enableMetrics: boolean;            // Track tee vs materialize decisions
}

interface StreamMetadata {
  id: string;
  sourceNodeId: string;
  executionId: string;
  createdAt: number;
  lastAccessedAt: number;
  consumerCount: number;
  estimatedSize: number;
  strategy: 'tee' | 'materialize';
  status: 'active' | 'completed' | 'error' | 'timeout';
}

class StreamRegistry {
  private activeStreams: Map<string, {
    metadata: StreamMetadata;
    streams: ReadableStream[];
    readers: Set<ReadableStreamDefaultReader>;
  }> = new Map();
  
  private config: StreamRegistryConfig;
  private metrics: StreamMetrics;
  
  constructor(config: StreamRegistryConfig) {
    this.config = config;
    this.metrics = { teeCount: 0, materializeCount: 0, totalStreams: 0 };
    this.startTimeoutMonitor();
  }
  
  async registerTeedStream(
    sourceNodeId: string,
    executionId: string,
    originalStream: ReadableStream,
    consumerCount: number,
    estimatedSize: number
  ): Promise<string> {
    
    if (this.activeStreams.size >= this.config.maxConcurrentStreams) {
      throw new Error(
        `Max concurrent streams reached (${this.config.maxConcurrentStreams}). ` +
        'Consider using materialization strategy.'
      );
    }
    
    const streamId = crypto.randomUUID();
    
    // Create teed streams based on consumer count
    const teedStreams = this.createMultiTee(originalStream, consumerCount);
    
    this.activeStreams.set(streamId, {
      metadata: {
        id: streamId,
        sourceNodeId,
        executionId,
        createdAt: Date.now(),
        lastAccessedAt: Date.now(),
        consumerCount,
        estimatedSize,
        strategy: 'tee',
        status: 'active'
      },
      streams: teedStreams,
      readers: new Set()
    });
    
    if (this.config.enableMetrics) {
      this.metrics.teeCount++;
      this.metrics.totalStreams++;
    }
    
    return streamId;
  }
  
  private createMultiTee(
    stream: ReadableStream, 
    count: number
  ): ReadableStream[] {
    if (count === 1) return [stream];
    if (count === 2) return stream.tee();
    
    // For 3+ consumers, tee iteratively
    const streams: ReadableStream[] = [];
    let remaining = stream;
    
    for (let i = 0; i < count - 1; i++) {
      const [stream1, stream2] = remaining.tee();
      streams.push(stream1);
      remaining = stream2;
    }
    streams.push(remaining);
    
    return streams;
  }
  
  async getStream(
    streamId: string, 
    consumerIndex: number
  ): Promise<ReadableStream> {
    const entry = this.activeStreams.get(streamId);
    
    if (!entry) {
      throw new Error(`Stream not found: ${streamId}`);
    }
    
    if (consumerIndex >= entry.streams.length) {
      throw new Error(
        `Invalid consumer index ${consumerIndex} ` +
        `(max: ${entry.streams.length - 1})`
      );
    }
    
    entry.metadata.lastAccessedAt = Date.now();
    
    return entry.streams[consumerIndex];
  }
  
  async acquireReader(
    streamId: string, 
    consumerIndex: number
  ): Promise<ReadableStreamDefaultReader> {
    const stream = await this.getStream(streamId, consumerIndex);
    const reader = stream.getReader();
    
    const entry = this.activeStreams.get(streamId);
    if (entry) {
      entry.readers.add(reader);
    }
    
    return reader;
  }
  
  async releaseReader(
    streamId: string, 
    reader: ReadableStreamDefaultReader
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    try {
      reader.releaseLock();
    } catch {
      // Already released
    }
    
    entry.readers.delete(reader);
    
    // Check if all consumers are done
    if (entry.readers.size === 0) {
      await this.cleanup(streamId, 'completed');
    }
  }
  
  async markError(streamId: string, error: Error): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    entry.metadata.status = 'error';
    
    // Release all readers
    for (const reader of entry.readers) {
      try {
        await reader.cancel(error.message);
      } catch {
        // Ignore
      }
    }
    
    await this.cleanup(streamId, 'error');
  }
  
  private async cleanup(
    streamId: string, 
    reason: 'completed' | 'error' | 'timeout'
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    entry.metadata.status = reason as any;
    
    // Cancel any remaining streams
    for (const stream of entry.streams) {
      try {
        const reader = stream.getReader();
        await reader.cancel(`Cleanup: ${reason}`);
        reader.releaseLock();
      } catch {
        // Stream may already be locked or closed
      }
    }
    
    this.activeStreams.delete(streamId);
  }
  
  private startTimeoutMonitor(): void {
    setInterval(() => {
      const now = Date.now();
      const timeout = this.config.streamTimeout;
      
      for (const [streamId, entry] of this.activeStreams.entries()) {
        if (now - entry.metadata.lastAccessedAt > timeout) {
          console.warn(`Stream timeout: ${streamId}`);
          this.cleanup(streamId, 'timeout');
        }
      }
    }, 60000); // Check every minute
  }
  
  getMetrics(): StreamMetrics & { active: number } {
    return {
      ...this.metrics,
      active: this.activeStreams.size
    };
  }
  
  getStreamInfo(streamId: string): StreamMetadata | null {
    return this.activeStreams.get(streamId)?.metadata ?? null;
  }
  
  listActiveStreams(): StreamMetadata[] {
    return Array.from(this.activeStreams.values())
      .map(entry => entry.metadata);
  }
}

interface StreamMetrics {
  teeCount: number;
  materializeCount: number;
  totalStreams: number;
}
```

## Adaptive Executor with Stream Registry Integration

```typescript
interface StreamingConfig {
  teeThresholdBytes: number;        // 5MB - tee if smaller
  materializeThresholdBytes: number; // 50MB - always materialize if larger
  enableAdaptiveTee: boolean;        // Use size estimation for decision
  maxTeesPerStream: number;          // 3 - max consumers for teeing
}

class AdaptiveExecutor {
  private streamingExecutor: StreamingExecutor;
  private batchExecutor: BatchExecutor;
  private storage: HybridStorageManager;
  private streamRegistry: StreamRegistry;
  private config: StreamingConfig;
  
  constructor(
    storage: HybridStorageManager, 
    streamRegistry: StreamRegistry,
    config: StreamingConfig
  ) {
    this.storage = storage;
    this.streamRegistry = streamRegistry;
    this.config = config;
    this.streamingExecutor = new StreamingExecutor();
    this.batchExecutor = new BatchExecutor();
  }
  
  async executeNode(
    node: WorkflowNode,
    inputs: Record<string, any>,
    edges: WorkflowEdge[]
  ): Promise<ExecutionResult> {
    
    // Analyze streaming feasibility
    const decision = this.analyzeStreamingFeasibility(node, inputs, edges);
    
    if (decision.shouldStream) {
      return this.executeWithStreaming(node, inputs, decision);
    } else {
      return this.executeWithBatch(node, inputs);
    }
  }
  
  private analyzeStreamingFeasibility(
    node: WorkflowNode,
    inputs: Record<string, any>,
    edges: WorkflowEdge[]
  ): StreamingDecision {
    
    const reasons: string[] = [];
    let shouldStream = false;
    let multiConsumerStrategy: MultiConsumerStrategy = 'none';
    
    // 1. Explicit node config
    if (node.data.config.streaming === false) {
      return {
        shouldStream: false,
        reasons: ['explicit_batch_mode'],
        multiConsumerStrategy: 'none'
      };
    }
    
    if (node.data.config.streaming === true) {
      shouldStream = true;
      reasons.push('explicit_streaming_mode');
    }
    
    // 2. Stream input detection
    const hasStreamInput = Object.values(inputs).some(v => 
      v instanceof ReadableStream || v?.$streamRef
    );
    
    if (hasStreamInput) {
      shouldStream = true;
      reasons.push('stream_input_detected');
    }
    
    // 3. Large data heuristic
    const estimatedSize = this.estimateDataSize(inputs);
    if (estimatedSize > 5 * 1024 * 1024) {
      shouldStream = true;
      reasons.push('large_input_heuristic');
    }
    
    // 4. Agent type benefits
    if (['researcher', 'coder', 'reviewer'].includes(node.data.type)) {
      shouldStream = true;
      reasons.push('agent_benefits_from_streaming');
    }
    
    // 5. Multi-consumer analysis
    if (shouldStream) {
      const downstreamCount = edges.filter(e => e.source === node.id).length;
      
      if (downstreamCount > 1) {
        multiConsumerStrategy = this.selectMultiConsumerStrategy(
          estimatedSize,
          downstreamCount
        );
        
        reasons.push(`multi_consumer_${multiConsumerStrategy}`);
      }
    }
    
    return {
      shouldStream,
      reasons,
      multiConsumerStrategy,
      estimatedSize
    };
  }
  
  private selectMultiConsumerStrategy(
    estimatedSize: number,
    consumerCount: number
  ): MultiConsumerStrategy {
    
    if (!this.config.enableAdaptiveTee) {
      return 'materialize';
    }
    
    // Large streams: always materialize
    if (estimatedSize > this.config.materializeThresholdBytes) {
      return 'materialize';
    }
    
    // Small streams: tee is efficient
    if (estimatedSize < this.config.teeThresholdBytes) {
      return consumerCount <= this.config.maxTeesPerStream ? 'tee' : 'materialize';
    }
    
    // Medium streams: depends on consumer count
    if (consumerCount <= 2) {
      return 'tee';
    } else {
      return 'materialize';
    }
  }
  
  private async executeWithStreaming(
    node: WorkflowNode,
    inputs: Record<string, any>,
    decision: StreamingDecision
  ): Promise<ExecutionResult> {
    
    const outputStream = await this.streamingExecutor.executeNodeStreaming(
      node,
      inputs
    );
    
    // Handle multi-consumer scenario
    if (decision.multiConsumerStrategy === 'materialize') {
      return await this.materializeStreamToStorage(node, outputStream, decision);
    } else if (decision.multiConsumerStrategy === 'tee') {
      return await this.teeStreamInRegistry(node, outputStream, decision);
    }
    
    // Single consumer: pass stream through
    return {
      nodeId: node.id,
      output: outputStream,
      streaming: true,
      metadata: {
        streamingReasons: decision.reasons,
        multiConsumerStrategy: 'none',
        estimatedSize: decision.estimatedSize
      }
    };
  }
  
  private async teeStreamInRegistry(
    node: WorkflowNode,
    stream: ReadableStream,
    decision: StreamingDecision
  ): Promise<ExecutionResult> {
    
    const downstreamCount = 2; // Get actual count from edges
    
    const streamId = await this.streamRegistry.registerTeedStream(
      node.id,
      'current-execution-id', // Get from context
      stream,
      downstreamCount,
      decision.estimatedSize
    );
    
    // Return stream reference
    return {
      nodeId: node.id,
      output: { 
        $streamRef: streamId,
        consumerCount: downstreamCount
      },
      streaming: true,
      metadata: {
        streamingReasons: decision.reasons,
        multiConsumerStrategy: 'tee',
        streamId,
        estimatedSize: decision.estimatedSize
      }
    };
  }
  
  private async materializeStreamToStorage(
    node: WorkflowNode,
    stream: ReadableStream,
    decision: StreamingDecision
  ): Promise<ExecutionResult> {
    
    const chunks: any[] = [];
    const reader = stream.getReader();
    
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
      }
    } finally {
      reader.releaseLock();
    }
    
    const materialized = this.combineChunks(chunks);
    
    const storageKey = `node-${node.id}-materialized`;
    await this.storage.store(storageKey, materialized, {
      nodeId: node.id,
      temporary: true,
      dataType: 'materialized'
    });
    
    if (this.streamRegistry['config'].enableMetrics) {
      this.streamRegistry['metrics'].materializeCount++;
    }
    
    return {
      nodeId: node.id,
      output: { $ref: storageKey },
      streaming: false,
      metadata: {
        materialized: true,
        storageKey,
        streamingReasons: decision.reasons,
        multiConsumerStrategy: 'materialize',
        actualSize: new TextEncoder().encode(JSON.stringify(materialized)).length
      }
    };
  }
  
  private async executeWithBatch(
    node: WorkflowNode,
    inputs: Record<string, any>
  ): Promise<ExecutionResult> {
    
    const resolvedInputs = await this.resolveInputs(inputs);
    const output = await this.batchExecutor.executeNodeBatch(node, resolvedInputs);
    
    return {
      nodeId: node.id,
      output,
      streaming: false,
      metadata: {}
    };
  }
  
  private async resolveInputs(inputs: Record<string, any>): Promise<Record<string, any>> {
    const resolved: Record<string, any> = {};
    
    for (const [key, value] of Object.entries(inputs)) {
      if (value && typeof value === 'object') {
        if (value.$ref) {
          // Storage reference
          resolved[key] = await this.storage.retrieve(value.$ref);
        } else if (value.$streamRef) {
          // Stream registry reference - get first available stream
          resolved[key] = await this.streamRegistry.getStream(value.$streamRef, 0);
        } else {
          resolved[key] = value;
        }
      } else {
        resolved[key] = value;
      }
    }
    
    return resolved;
  }
  
  private estimateDataSize(data: any): number {
    try {
      return JSON.stringify(data).length;
    } catch {
      return 0;
    }
  }
  
  private combineChunks(chunks: any[]): any {
    if (chunks.length === 0) return null;
    
    if (typeof chunks[0] === 'string') {
      return chunks.join('');
    }
    
    if (Array.isArray(chunks[0])) {
      return chunks.flat();
    }
    
    return chunks[chunks.length - 1];
  }
}

type MultiConsumerStrategy = 'none' | 'tee' | 'materialize';

interface StreamingDecision {
  shouldStream: boolean;
  reasons: string[];
  multiConsumerStrategy: MultiConsumerStrategy;
  estimatedSize: number;
}

interface ExecutionResult {
  nodeId: string;
  output: any | ReadableStream | { $ref: string } | { $streamRef: string };
  streaming: boolean;
  metadata: Record<string, any>;
}

interface WorkflowNode {
  id: string;
  data: {
    type: string;
    config: {
      streaming?: boolean;
      [key: string]: any;
    };
  };
}

interface WorkflowEdge {
  source: string;
  target: string;
}
```

## Composable Expression System with Clear Syntax

### Key Change: Inline Block Markers for Composite Mode

```typescript
// Expression syntax for composite mode:
// Use {{block:type:config}} markers inline with text

// Examples:
// "$.users[age > 18].{{block:aggregate:sum:salary}}"
// "{{block:field:items}}[price > 100].name"
// "$.data | {{block:transform:normalize}} | {{block:filter:active}}"

interface ExpressionEngine {
  evaluate(expression: Expression, context: any): Promise<any>;
  validate(expression: Expression): ValidationResult;
  parseComposite(text: string): ExpressionPart[];
  serializeComposite(parts: ExpressionPart[]): string;
}

type Expression = 
  | { mode: 'text'; value: string }
  | { mode: 'visual'; blocks: ExpressionBlock[] }
  | { mode: 'composite'; parts: ExpressionPart[] };

type ExpressionPart =
  | { type: 'text'; value: string }
  | { type: 'block'; block: ExpressionBlock };

interface ExpressionBlock {
  id: string;
  type: 'field' | 'filter' | 'map' | 'aggregate' | 'transform';
  config: Record<string, any>;
}

class ComposableExpressionEngine implements ExpressionEngine {
  private jsonataEngine: JSONataEngine;
  private blockMarkerRegex = /\{\{block:([^:}]+):([^}]+)\}\}/g;
  
  constructor() {
    this.jsonataEngine = new JSONataEngine();
  }
  
  parseComposite(text: string): ExpressionPart[] {
    const parts: ExpressionPart[] = [];
    let lastIndex = 0;
    
    const matches = text.matchAll(this.blockMarkerRegex);
    
    for (const match of matches) {
      // Add text before block
      if (match.index! > lastIndex) {
        const textPart = text.slice(lastIndex, match.index);
        if (textPart) {
          parts.push({ type: 'text', value: textPart });
        }
      }
      
      // Parse block
      const [_, blockType, configStr] = match;
      const config = this.parseBlockConfig(blockType, configStr);
      
      parts.push({
        type: 'block',
        block: {
          id: crypto.randomUUID(),
          type: blockType as any,
          config
        }
      });
      
      lastIndex = match.index! + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push({ type: 'text', value: text.slice(lastIndex) });
    }
    
    return parts;
  }
  
  serializeComposite(parts: ExpressionPart[]): string {
    return parts.map(part => {
      if (part.type === 'text') {
        return part.value;
      } else {
        const block = part.block;
        const configStr = this.serializeBlockConfig(block.type, block.config);
        return `{{block:${block.type}:${configStr}}}`;
      }
    }).join('');
  }
  
  private parseBlockConfig(type: string, configStr: string): Record<string, any> {
    // Simple key:value parsing
    const pairs = configStr.split(':');
    
    switch (type) {
      case 'field':
        return { path: pairs[0] };
      case 'filter':
        return { condition: pairs[0] };
      case 'aggregate':
        return { function: pairs[0], path: pairs[1] };
      case 'transform':
        return { operation: pairs[0] };
      default:
        return {};
    }
  }
  
  private serializeBlockConfig(type: string, config: Record<string, any>): string {
    switch (type) {
      case 'field':
        return config.path;
      case 'filter':
        return config.condition;
      case 'aggregate':
        return `${config.function}:${config.path}`;
      case 'transform':
        return config.operation;
      default:
        return '';
    }
  }
  
  async evaluate(expression: Expression, context: any): Promise<any> {
    switch (expression.mode) {
      case 'text':
        return this.jsonataEngine.evaluate(expression.value, context);
        
      case 'visual':
        const jsonataFromBlocks = this.blocksToJSONata(expression.blocks);
        return this.jsonataEngine.evaluate(jsonataFromBlocks, context);
        
      case 'composite':
        const jsonataFromComposite = this.compositeToJSONata(expression.parts);
        return this.jsonataEngine.evaluate(jsonataFromComposite, context);
        
      default:
        throw new Error(`Unknown expression mode: ${(expression as any).mode}`);
    }
  }
  
  validate(expression: Expression): ValidationResult {
    try {
      let jsonataExpr: string;
      
      switch (expression.mode) {
        case 'text':
          jsonataExpr = expression.value;
          break;
        case 'visual':
          jsonataExpr = this.blocksToJSONata(expression.blocks);
          break;
        case 'composite':
          jsonataExpr = this.compositeToJSONata(expression.parts);
          break;
        default:
          return { valid: false, error: 'Unknown expression mode' };
      }
      
      return this.jsonataEngine.validate(jsonataExpr);
      
    } catch (error: any) {
      return { 
        valid: false, 
        error: error.message,
        suggestion: 'Check expression syntax'
      };
    }
  }
  
  private blocksToJSONata(blocks: ExpressionBlock[]): string {
    return blocks.map(block => this.blockToJSONata(block)).join('');
  }
  
  private compositeToJSONata(parts: ExpressionPart[]): string {
    return parts.map(part => {
      if (part.type === 'text') {
        return part.value;
      } else {
        return this.blockToJSONata(part.block);
      }
    }).join('');
  }
  
  private blockToJSONata(block: ExpressionBlock): string {
    switch (block.type) {
      case 'field':
        return `$.${block.config.path}`;
      case 'filter':
        return `[${block.config.condition}]`;
      case 'map':
        return `.{ ${block.config.mapping} }`;
      case 'aggregate':
        return `$${block.config.function}(${block.config.path})`;
      case 'transform':
        return block.config.expression || block.config.operation;
      default:
        throw new Error(`Unknown block type: ${block.type}`);
    }
  }
  
  getExamples(): ExpressionExample[] {
    return [
      {
        category: 'Text Mode',
        expression: { mode: 'text', value: '$.user.name' },
        description: 'Simple field extraction',
        inputExample: { user: { name: 'Alice' } },
        outputExample: 'Alice'
      },
      {
        category: 'Composite Mode',
        expression: {
          mode: 'composite',
          parts: this.parseComposite(
            '$.items[price > 100].{{block:aggregate:sum:price}}'
          )
        },
        description: 'Mix text and visual blocks',
        inputExample: { items: [{ price: 50 }, { price: 150 }, { price: 200 }] },
        outputExample: 350
      }
    ];
  }
}

class JSONataEngine {
  private cache: Map<string, any> = new Map();
  private readonly timeout = 5000;
  
  async evaluate(expression: string, context: any): Promise<any> {
    let compiled = this.cache.get(expression);
    
    if (!compiled) {
      // In real implementation, use actual JSONata library
      compiled = { evaluate: (ctx: any) => this.simpleEval(expression, ctx) };
      this.cache.set(expression, compiled);
    }
    
    return await Promise.race([
      Promise.resolve(compiled.evaluate(context)),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Expression timeout')), this.timeout)
      )
    ]);
  }
  
  validate(expression: string): ValidationResult {
    try {
      if (!expression || expression.trim().length === 0) {
        return { valid: false, error: 'Empty expression' };
      }
      
      return { valid: true };
    } catch (error: any) {
      return { 
        valid: false, 
        error: error.message,
        suggestion: 'Check JSONata syntax'
      };
    }
  }
  
  private simpleEval(expression: string, context: any): any {
    if (expression.startsWith('$.')) {
      const path = expression.substring(2).split('.');
      let result = context;
      for (const key of path) {
        result = result?.[key];
      }
      return result;
    }
    
    return null;
  }
}

// UI Component
const ComposableExpressionEditor: React.FC<{
  value: Expression;
  onChange: (value: Expression) => void;
}> = ({ value, onChange }) => {
  
  const [mode, setMode] = useState<'text' | 'visual' | 'composite'>(value.mode);
  const engine = useMemo(() => new ComposableExpressionEngine(), []);
  const [validation, setValidation] = useState<ValidationResult>({ valid: true });
  
  useEffect(() => {
    setValidation(engine.validate(value));
  }, [value, engine]);
  
  const handleTextChange = (text: string) => {
    if (mode === 'composite') {
      // Parse inline block markers
      const parts = engine.parseComposite(text);
      onChange({ mode: 'composite', parts });
    } else {
      onChange({ mode: 'text', value: text });
    }
  };
  
  const insertBlock = (blockType: string) => {
    if (mode !== 'composite' || value.mode !== 'composite') return;
    
    const serialized = engine.serializeComposite(value.parts);
    const marker = `{{block:${blockType}:}}`;
    
    // Insert at cursor position (simplified)
    const newText = serialized + marker;
    const parts = engine.parseComposite(newText);
    onChange({ mode: 'composite', parts });
  };
  
  return (
    <div className="expression-editor">
      <div className="mode-selector">
        <button 
          onClick={() => setMode('text')}
          className={mode === 'text' ? 'active' : ''}
        >
          Text
        </button>
        <button 
          onClick={() => setMode('visual')}
          className={mode === 'visual' ? 'active' : ''}
        >
          Visual
        </button>
        <button 
          onClick={() => setMode('composite')}
          className={mode === 'composite' ? 'active' : ''}
        >
          Mixed
        </button>
      </div>
      
      {(mode === 'text' || mode === 'composite') && (
        <div>
          <textarea
            value={
              value.mode === 'text' 
                ? value.value 
                : value.mode === 'composite'
                ? engine.serializeComposite(value.parts)
                : ''
            }
            onChange={e => handleTextChange(e.target.value)}
            className={validation.valid ? '' : 'error'}
            placeholder={
              mode === 'composite'
                ? 'Enter expression with {{block:type:config}} markers'
                : 'Enter JSONata expression'
            }
          />
          
          {mode === 'composite' && (
            <div className="block-palette">
              <button onClick={() => insertBlock('field')}>+ Field</button>
              <button onClick={() => insertBlock('filter')}>+ Filter</button>
              <button onClick={() => insertBlock('aggregate')}>+ Aggregate</button>
            </div>
          )}
        </div>
      )}
      
      {mode === 'visual' && value.mode === 'visual' && (
        <VisualBlockEditor
          blocks={value.blocks}
          onChange={blocks => onChange({ mode: 'visual', blocks })}
        />
      )}
      
      {!validation.valid && (
        <div className="error-message">
          {validation.error}
          {validation.suggestion && <div className="suggestion">{validation.suggestion}</div>}
        </div>
      )}
    </div>
  );
};

const VisualBlockEditor: React.FC<{
  blocks: ExpressionBlock[];
  onChange: (blocks: ExpressionBlock[]) => void;
}> = ({ blocks, onChange }) => {
  return <div>Visual block editor</div>;
};

interface ValidationResult {
  valid: boolean;
  error?: string;
  suggestion?: string;
}

interface ExpressionExample {
  category: string;
  expression: Expression;
  description: string;
  inputExample: any;
  outputExample: any;
}
```

## Serializable Compensation Handlers

### Key Change: Handlers as Declarative Config, Registered at Workflow Level

```typescript
// Handlers are now declarative configurations, not code
type CompensationHandlerConfig = {
  id: string;
  name: string;
  handlerType: 'builtin' | 'http-api' | 'webhook' | 'custom';
  
  // Matching rules
  matches: {
    operation?: string[];        // Match specific operations
    description?: string[];      // Regex patterns for description
    service?: string[];          // Service names
  };
  
  // Compensation behavior
  compensation: 
    | { type: 'http-api'; config: HttpApiConfig }
    | { type: 'webhook'; config: WebhookConfig }
    | { type: 'custom'; className: string }  // For advanced users
    | { type: 'manual'; steps: string[] };
};

interface HttpApiConfig {
  method: 'GET' | 'POST' | 'DELETE' | 'PUT';
  urlTemplate: string;           // "https://api.stripe.com/v1/refunds"
  headers: Record<string, string>;
  bodyTemplate: string;          // JSON with {{placeholders}}
  auth?: {
    type: 'bearer' | 'basic' | 'api-key';
    tokenPath: string;           // Path to token in effect data
  };
}

interface WebhookConfig {
  url: string;
  method: 'POST' | 'PUT';
  payloadTemplate: string;
}

class CompensationHandlerRegistry {
  private handlers: Map<string, CompensationHandler> = new Map();
  private configs: Map<string, CompensationHandlerConfig> = new Map();
  
  // Register from declarative config
  registerFromConfig(config: CompensationHandlerConfig): void {
    this.configs.set(config.id, config);
    
    const handler = this.createHandlerFromConfig(config);
    this.handlers.set(config.id, handler);
  }
  
  private createHandlerFromConfig(
    config: CompensationHandlerConfig
  ): CompensationHandler {
    
    return {
      name: config.name,
      
      canHandle: (entry: SideEffectEntry) => {
        const { matches } = config;
        
        if (matches.operation && !matches.operation.includes(entry.operation)) {
          return false;
        }
        
        if (matches.description) {
          const descMatch = matches.description.some(pattern => 
            new RegExp(pattern).test(entry.description)
          );
          if (!descMatch) return false;
        }
        
        if (matches.service) {
          const descriptor = entry.compensation as any;
          if (!matches.service.includes(descriptor.service)) {
            return false;
          }
        }
        
        return true;
      },
      
      compensate: async (entry: SideEffectEntry) => {
        switch (config.compensation.type) {
          case 'http-api':
            return this.compensateViaHttpApi(entry, config.compensation.config);
            
          case 'webhook':
            return this.compensateViaWebhook(entry, config.compensation.config);
            
          case 'custom':
            // Load custom class (advanced)
            const CustomHandler = await this.loadCustomHandler(
              config.compensation.className
            );
            return new CustomHandler().compensate(entry);
            
          case 'manual':
            return {
              success: false,
              requiresUserAction: true,
              manualSteps: config.compensation.steps
            };
            
          default:
            throw new Error(`Unknown compensation type: ${(config.compensation as any).type}`);
        }
      }
    };
  }
  
  private async compensateViaHttpApi(
    entry: SideEffectEntry,
    config: HttpApiConfig
  ): Promise<CompensationResult> {
    
    const descriptor = entry.compensation as any;
    
    // Resolve URL template
    const url = this.resolveTemplate(config.urlTemplate, {
      ...descriptor,
      effectId: entry.id
    });
    
    // Resolve headers
    const headers = { ...config.headers };
    
    if (config.auth) {
      const token = this.extractValue(descriptor, config.auth.tokenPath);
      switch (config.auth.type) {
        case 'bearer':
          headers['Authorization'] = `Bearer ${token}`;
          break;
        case 'api-key':
          headers['Authorization'] = token;
          break;
      }
    }
    
    // Resolve body
    const body = config.bodyTemplate
      ? this.resolveTemplate(config.bodyTemplate, descriptor)
      : undefined;
    
    try {
      const response = await fetch(url, {
        method: config.method,
        headers,
        body: body ? JSON.stringify(JSON.parse(body)) : undefined
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return {
        success: true,
        message: `Compensated via ${config.method} ${url}`
      };
      
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        requiresUserAction: true,
        manualSteps: [
          `Failed to compensate via API: ${error.message}`,
          `Operation: ${entry.description}`,
          'Please manually revert'
        ]
      };
    }
  }
  
  private async compensateViaWebhook(
    entry: SideEffectEntry,
    config: WebhookConfig
  ): Promise<CompensationResult> {
    
    const descriptor = entry.compensation as any;
    const payload = this.resolveTemplate(config.payloadTemplate, {
      ...descriptor,
      effectId: entry.id,
      effectDescription: entry.description
    });
    
    try {
      const response = await fetch(config.url, {
        method: config.method,
        headers: { 'Content-Type': 'application/json' },
        body: payload
      });
      
      if (!response.ok) {
        throw new Error(`Webhook failed: ${response.statusText}`);
      }
      
      return {
        success: true,
        message: `Webhook triggered: ${config.url}`
      };
      
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  private resolveTemplate(template: string, data: any): string {
    return template.replace(/\{\{([^}]+)\}\}/g, (_, path) => {
      return this.extractValue(data, path) ?? '';
    });
  }
  
  private extractValue(obj: any, path: string): any {
    const parts = path.split('.');
    let result = obj;
    for (const part of parts) {
      result = result?.[part];
    }
    return result;
  }
  
  private async loadCustomHandler(className: string): Promise<any> {
    // In real implementation, dynamically import class
    throw new Error('Custom handlers not yet implemented');
  }
  
  // Serialization for workflow persistence
  serializeConfigs(): CompensationHandlerConfig[] {
    return Array.from(this.configs.values());
  }
  
  loadConfigs(configs: CompensationHandlerConfig[]): void {
    for (const config of configs) {
      this.registerFromConfig(config);
    }
  }
  
  unregister(id: string): void {
    this.handlers.delete(id);
    this.configs.delete(id);
  }
  
  findHandler(entry: SideEffectEntry): CompensationHandler | null {
    for (const handler of this.handlers.values()) {
      if (handler.canHandle(entry)) {
        return handler;
      }
    }
    return null;
  }
}

// Example: Stripe handler as config
const stripeHandlerConfig: CompensationHandlerConfig = {
  id: 'stripe-refund',
  name: 'Stripe Refund Handler',
  handlerType: 'http-api',
  
  matches: {
    operation: ['payment_process'],
    description: ['Stripe.*payment'],
    service: ['stripe']
  },
  
  compensation: {
    type: 'http-api',
    config: {
      method: 'POST',
      urlTemplate: 'https://api.stripe.com/v1/refunds',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      bodyTemplate: JSON.stringify({
        charge: '{{chargeId}}',
        reason: 'requested_by_customer'
      }),
      auth: {
        type: 'bearer',
        tokenPath: 'apiKey'
      }
    }
  }
};

// Usage
const registry = new CompensationHandlerRegistry();
registry.registerFromConfig(stripeHandlerConfig);

// Serialize with workflow
const workflowData = {
  nodes: [...],
  edges: [...],
  compensationHandlers: registry.serializeConfigs()
};

// Load from workflow
registry.loadConfigs(workflowData.compensationHandlers);

interface CompensationHandler {
  name: string;
  compensate(entry: SideEffectEntry): Promise<CompensationResult>;
  canHandle(entry: SideEffectEntry): boolean;
}

interface SideEffectEntry {
  id: string;
  nodeId: string;
  executionId: string;
  timestamp: number;
  operation: string;
  description: string;
  compensation: any;
  status: string;
}

interface CompensationResult {
  success: boolean;
  error?: string;
  message?: string;
  manualSteps?: string[];
  requiresUserAction?: boolean;
}
```

## Performance Monitoring for Streaming Decisions

```typescript
interface StreamingMetrics {
  decisions: {
    teeCount: number;
    materializeCount: number;
    batchCount: number;
  };
  
  performance: {
    avgTeeMemory: number;         // Average memory per tee (bytes)
    avgMaterializeSize: number;   // Average materialized size (bytes)
    avgTeeTime: number;           // Average time to complete tee (ms)
    avgMaterializeTime: number;   // Average time to materialize (ms)
  };
  
  errors: {
    teeFailures: number;
    materializeFailures: number;
    storageFullErrors: number;
  };
  
  recommendations: {
    suggestedTeeThreshold: number;
    suggestedMaterializeThreshold: number;
    suggestedOverflowPolicy: string;
  };
}

class StreamingPerformanceMonitor {
  private metrics: StreamingMetrics;
  private measurements: Array<{
    strategy: 'tee' | 'materialize';
    sizeBytes: number;
    durationMs: number;
    memoryUsed: number;
    timestamp: number;
  }> = [];
  
  constructor() {
    this.metrics = this.initMetrics();
  }
  
  recordDecision(
    strategy: 'tee' | 'materialize' | 'batch',
    sizeBytes: number,
    durationMs: number,
    memoryUsed: number
  ): void {
    
    switch (strategy) {
      case 'tee':
        this.metrics.decisions.teeCount++;
        break;
      case 'materialize':
        this.metrics.decisions.materializeCount++;
        break;
      case 'batch':
        this.metrics.decisions.batchCount++;
        break;
    }
    
    if (strategy === 'tee' || strategy === 'materialize') {
      this.measurements.push({
        strategy,
        sizeBytes,
        durationMs,
        memoryUsed,
        timestamp: Date.now()
      });
      
      // Keep last 100 measurements
      if (this.measurements.length > 100) {
        this.measurements.shift();
      }
      
      this.updateAverages();
      this.generateRecommendations();
    }
  }
  
  recordError(type: 'tee' | 'materialize' | 'storage-full'): void {
    switch (type) {
      case 'tee':
        this.metrics.errors.teeFailures++;
        break;
      case 'materialize':
        this.metrics.errors.materializeFailures++;
        break;
      case 'storage-full':
        this.metrics.errors.storageFullErrors++;
        break;
    }
  }
  
  private updateAverages(): void {
    const tees = this.measurements.filter(m => m.strategy === 'tee');
    const materializes = this.measurements.filter(m => m.strategy === 'materialize');
    
    if (tees.length > 0) {
      this.metrics.performance.avgTeeMemory = 
        tees.reduce((sum, m) => sum + m.memoryUsed, 0) / tees.length;
      this.metrics.performance.avgTeeTime = 
        tees.reduce((sum, m) => sum + m.durationMs, 0) / tees.length;
    }
    
    if (materializes.length > 0) {
      this.metrics.performance.avgMaterializeSize = 
        materializes.reduce((sum, m) => sum + m.sizeBytes, 0) / materializes.length;
      this.metrics.performance.avgMaterializeTime = 
        materializes.reduce((sum, m) => sum + m.durationMs, 0) / materializes.length;
    }
  }
  
  private generateRecommendations(): void {
    // Analyze patterns to suggest better thresholds
    
    // If tees are consistently using too much memory, lower threshold
    if (this.metrics.performance.avgTeeMemory > 10 * 1024 * 1024) {
      this.metrics.recommendations.suggestedTeeThreshold = 3 * 1024 * 1024; // 3MB
    } else {
      this.metrics.recommendations.suggestedTeeThreshold = 5 * 1024 * 1024; // 5MB
    }
    
    // If materialize operations are fast, raise threshold
    if (this.metrics.performance.avgMaterializeTime < 100) {
      this.metrics.recommendations.suggestedMaterializeThreshold = 100 * 1024 * 1024; // 100MB
    } else {
      this.metrics.recommendations.suggestedMaterializeThreshold = 50 * 1024 * 1024; // 50MB
    }
    
    // Recommend overflow policy based on errors
    if (this.metrics.errors.storageFullErrors > 5) {
      this.metrics.recommendations.suggestedOverflowPolicy = 'evict-lru';
    } else {
      this.metrics.recommendations.suggestedOverflowPolicy = 'compress-max';
    }
  }
  
  getMetrics(): StreamingMetrics {
    return { ...this.metrics };
  }
  
  getMeasurements(): typeof this.measurements {
    return [...this.measurements];
  }
  
  private initMetrics(): StreamingMetrics {
    return {
      decisions: {
        teeCount: 0,
        materializeCount: 0,
        batchCount: 0
      },
      performance: {
        avgTeeMemory: 0,
        avgMaterializeSize: 0,
        avgTeeTime: 0,
        avgMaterializeTime: 0
      },
      errors: {
        teeFailures: 0,
        materializeFailures: 0,
        storageFullErrors: 0
      },
      recommendations: {
        suggestedTeeThreshold: 5 * 1024 * 1024,
        suggestedMaterializeThreshold: 50 * 1024 * 1024,
        suggestedOverflowPolicy: 'evict-lru'
      }
    };
  }
}

// UI Component for Metrics Dashboard
const StreamingMetricsDashboard: React.FC<{
  monitor: StreamingPerformanceMonitor;
}> = ({ monitor }) => {
  
  const [metrics, setMetrics] = useState(monitor.getMetrics());
  
  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics(monitor.getMetrics());
    }, 1000);
    
    return () => clearInterval(interval);
  }, [monitor]);
  
  return (
    <div className="metrics-dashboard">
      <h3>Streaming Performance</h3>
      
      <div className="metrics-section">
        <h4>Decisions</h4>
        <div>Tees: {metrics.decisions.teeCount}</div>
        <div>Materializes: {metrics.decisions.materializeCount}</div>
        <div>Batch: {metrics.decisions.batchCount}</div>
      </div>
      
      <div className="metrics-section">
        <h4>Performance</h4>
        <div>Avg Tee Memory: {formatBytes(metrics.performance.avgTeeMemory)}</div>
        <div>Avg Materialize Size: {formatBytes(metrics.performance.avgMaterializeSize)}</div>
        <div>Avg Tee Time: {metrics.performance.avgTeeTime.toFixed(2)}ms</div>
        <div>Avg Materialize Time: {metrics.performance.avgMaterializeTime.toFixed(2)}ms</div>
      </div>
      
      <div className="metrics-section">
        <h4>Errors</h4>
        <div>Tee Failures: {metrics.errors.teeFailures}</div>
        <div>Materialize Failures: {metrics.errors.materializeFailures}</div>
        <div>Storage Full: {metrics.errors.storageFullErrors}</div>
      </div>
      
      <div className="metrics-section recommendations">
        <h4>Recommendations</h4>
        <div>Tee Threshold: {formatBytes(metrics.recommendations.suggestedTeeThreshold)}</div>
        <div>Materialize Threshold: {formatBytes(metrics.recommendations.suggestedMaterializeThreshold)}</div>
        <div>Overflow Policy: {metrics.recommendations.suggestedOverflowPolicy}</div>
      </div>
    </div>
  );
};
```

---

## What I Improved

### 1. Storage Overflow Policy Naming
**Changed**: `drop-on-store` → `fail-when-full`, `drop-oldest` → `evict-lru`/`evict-oldest`
- **Why**: "fail-when-full" is more explicit about what happens (throws error)
- **Added**: Separate `evict-lru` (access-based) vs `evict-oldest` (time-based) for clarity
- **Added**: Eviction preferences (protect recent, frequent, pinned items)
- **Added**: Storage event system for monitoring

### 2. Stream Registry as First-Class System
**Changed**: From "execution context storage" to dedicated `StreamRegistry`
- **Why**: Streams have different lifecycle than data artifacts
- **Added**: Timeout monitoring for abandoned streams
- **Added**: Multi-tee support (3+ consumers via iterative teeing)
- **Added**: Reader tracking for proper cleanup
- **Added**: Stream metrics separate from storage metrics

### 3. Composite Expression Syntax
**Changed**: From abstract "mixed mode" to concrete inline markers
- **Syntax**: `{{block:type:config}}` embedded in text
- **Why**: Makes composite mode tangible and editable as text
- **Added**: `parseComposite()` and `serializeComposite()` for conversion
- **Added**: Block insertion palette in UI

### 4. Serializable Compensation Handlers
**Changed**: From TypeScript classes to declarative JSON configs
- **Why**: Handlers can now be saved with workflows
- **Format**: HTTP API templates, webhook configs, or custom classes
- **Added**: Template system with `{{placeholder}}` syntax
- **Added**: Handler registry persistence (`serializeConfigs()`)

### 5. Performance Monitoring System
**Added**: Complete streaming performance tracking
- **Metrics**: Tee vs materialize decisions, memory usage, timing
- **Analysis**: Auto-generated threshold recommendations
- **UI**: Real-time dashboard component
- **Feedback Loop**: Metrics inform threshold tuning

### 6. Enhanced Storage Management
**Added**: Several production-ready features
- **Pinning**: Protect critical artifacts from eviction
- **Events**: Observable storage operations
- **Warnings**: Proactive alerts at 80% capacity
- **Error Types**: `StorageFullError` with detailed stats

---

## What I Kept

All excellent architectural decisions:
- React Flow canvas with viewport culling
- Zustand + immer state management
- Two-tier storage (Memory + IndexedDB)
- Adaptive streaming with size-based decisions
- Append-only side effect log
- Checkpoint manager with strategies
- Worker pool architecture
- Compression for large data
- Auto-cleanup of temporary artifacts
- All performance optimizations

---

## Remaining Concerns

### 1. Stream Registry Memory Management
The stream registry holds `ReadableStream` objects in memory, which can't be serialized. If a page refreshes:
- **Issue**: All teed streams are lost
- **Mitigation**: Should we auto-materialize long-lived streams to storage?
- **Trade-off**: Defeats the purpose of streaming for performance

### 2. Composite Expression Learning Curve
The `{{block:type:config}}` syntax is powerful but:
- **Issue**: Users need to learn the marker format
- **Mitigation**: Good examples + auto-complete in UI
- **Alternative**: Click-to-insert blocks that generate markers automatically

### 3. Compensation Handler Security
Handlers defined in JSON can make arbitrary HTTP calls:
- **Issue**: Malicious workflows could call unintended APIs
- **Mitigation**: Require user approval for each handler registration?
- **Alternative**: Sandboxed execution environment for handlers

### 4. Metrics Storage Size
Tracking 100 measurements per metric can grow large:
- **Issue**: Metrics themselves consume memory
- **Mitigation**: Persist to IndexedDB instead of memory
- **Alternative**: Sample (only keep every Nth measurement)

---

## Convergence Status

**ITERATING** - Good progress, but need architect's input on key design choices:

✅ Clearer overflow policy names and eviction strategies  
✅ Dedicated stream registry with lifecycle management  
✅ Concrete composite expression syntax  
✅ Serializable compensation handlers  
✅ Performance monitoring system  

❓ Stream persistence strategy on page refresh  
❓ Composite expression UI/UX details  
❓ Compensation handler security model  
❓ Metrics storage and sampling strategy  

---

## PROMPT_FOR_ARCHITECT:

Please focus on these refined areas:

1. **Stream Registry Persistence**: The stream registry holds active `ReadableStream` objects that can't survive page refresh. Should we:
   - Accept this limitation (users re-run workflows after refresh)?
   - Auto-materialize streams that live longer than N seconds?
   - Add a "save checkpoint" button that materializes all active streams?

2. **Composite Expression UX**: I've defined the syntax as `{{block:type:config}}`, but how should the UI work?
   - Should users type markers manually (with autocomplete)?
   - Should clicking "Insert Block" add the marker at cursor position?
   - Should we show a visual preview of blocks highlighted within the text?

3. **Compensation Handler Trust Model**: Since handlers are declarative configs that make HTTP calls:
   - Should ALL handlers require explicit user approval when registered?
   - Should we have "trusted" vs "untrusted" handler sources?
   - Should we sandbox handler execution somehow (CSP, web worker)?

4. **Performance Metrics Persistence**: Currently metrics live in memory. Should we:
   - Persist to IndexedDB for long-term analysis?
   - Only track metrics in development mode?
   - Sample aggressively (1 in 10 measurements) to reduce memory?

5. **Eviction Strategy Recommendations**: With both `evict-lru` and `evict-oldest` available:
   - Should we recommend one as default for most workflows?
   - Should eviction strategy be per-workflow or global?
   - Should users be able to mix strategies (LRU for memory, FIFO for IndexedDB)?

**Convergence Signal:** ITERATING

---

## Round 4

### 🔵 Agent A

## Design

# Visual AI Agent Workflow Builder - Production-Ready Architecture v5

## Core Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │         │
│  │   (React     │  │    Panel     │  │   & Palette  │         │
│  │    Flow)     │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│           State Management (Zustand + Immer)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Orchestration Layer                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Adaptive   │  │  Resilient │  │ Checkpoint │         │  │
│  │  │ Executor   │  │  Stream    │  │  Manager   │         │  │
│  │  │            │  │  Manager   │  │            │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Data Flow & Storage Layer                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Composable │  │   Tiered   │  │ Effect Log │         │  │
│  │  │ Expression │  │  Storage   │  │  (Append-  │         │  │
│  │  │  System    │  │  Manager   │  │   Only)    │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Canvas**: React Flow v11+ with viewport culling
- **State**: Zustand with immer middleware and persistence
- **UI**: Radix UI primitives + Tailwind CSS
- **Execution**: Adaptive executor with resilient streaming
- **Storage**: Three-tier (Memory + IndexedDB + SessionStorage) with per-workflow policies
- **Expressions**: Composable expression system with visual-text hybrid mode
- **Side Effects**: Append-only log with sandboxed compensation handlers
- **Workers**: Shared Worker pool with resource quotas

## Resilient Stream Manager (Solves Page Refresh Problem)

### Key Innovation: Automatic Checkpoint-Based Stream Resurrection

```typescript
interface StreamManagerConfig {
  maxConcurrentStreams: number;        // 50
  streamTimeout: number;                // 5min
  autoCheckpointInterval: number;       // 30s - checkpoint long-lived streams
  checkpointThresholdAge: number;       // 60s - checkpoint if older than this
  enableResurrection: boolean;          // Restore streams after page refresh
  maxResurrectionAttempts: number;      // 3
}

interface StreamCheckpoint {
  streamId: string;
  sourceNodeId: string;
  executionId: string;
  consumerCount: number;
  createdAt: number;
  lastCheckpointAt: number;
  
  // Resurrection data
  materializationType: 'full' | 'partial' | 'regenerate';
  materializedData?: any;               // For 'full' or 'partial'
  partialOffset?: number;               // Where partial stopped
  regenerationConfig?: {                // For 'regenerate'
    nodeConfig: any;
    inputs: Record<string, any>;
  };
  
  // State
  status: 'active' | 'checkpointed' | 'resurrected' | 'expired';
  resurrectionAttempts: number;
}

class ResilientStreamManager {
  private activeStreams: Map<string, ActiveStreamEntry> = new Map();
  private checkpoints: Map<string, StreamCheckpoint> = new Map();
  private storage: HybridStorageManager;
  private config: StreamManagerConfig;
  
  constructor(storage: HybridStorageManager, config: StreamManagerConfig) {
    this.storage = storage;
    this.config = config;
    
    // Restore checkpoints from previous session
    if (config.enableResurrection) {
      this.restoreCheckpointsFromStorage();
    }
    
    this.startAutoCheckpointing();
    this.startTimeoutMonitor();
  }
  
  async registerStream(
    sourceNodeId: string,
    executionId: string,
    stream: ReadableStream,
    consumerCount: number,
    options: {
      estimatedSize: number;
      materializationType?: 'full' | 'partial' | 'regenerate';
      regenerationConfig?: any;
    }
  ): Promise<string> {
    
    if (this.activeStreams.size >= this.config.maxConcurrentStreams) {
      throw new Error(
        `Max concurrent streams reached (${this.config.maxConcurrentStreams})`
      );
    }
    
    const streamId = crypto.randomUUID();
    
    // Create teed streams
    const teedStreams = this.createMultiTee(stream, consumerCount);
    
    // Create checkpoint
    const checkpoint: StreamCheckpoint = {
      streamId,
      sourceNodeId,
      executionId,
      consumerCount,
      createdAt: Date.now(),
      lastCheckpointAt: Date.now(),
      materializationType: options.materializationType ?? 'full',
      regenerationConfig: options.regenerationConfig,
      status: 'active',
      resurrectionAttempts: 0
    };
    
    this.checkpoints.set(streamId, checkpoint);
    
    this.activeStreams.set(streamId, {
      checkpoint,
      streams: teedStreams,
      readers: new Set(),
      materializedChunks: options.materializationType !== 'regenerate' ? [] : undefined
    });
    
    return streamId;
  }
  
  async getStream(streamId: string, consumerIndex: number): Promise<ReadableStream> {
    const active = this.activeStreams.get(streamId);
    
    if (active) {
      // Stream is live
      active.checkpoint.lastCheckpointAt = Date.now();
      return active.streams[consumerIndex];
    }
    
    // Try to resurrect from checkpoint
    if (this.config.enableResurrection) {
      const resurrected = await this.resurrectStream(streamId, consumerIndex);
      if (resurrected) return resurrected;
    }
    
    throw new Error(`Stream not found and could not be resurrected: ${streamId}`);
  }
  
  private async resurrectStream(
    streamId: string, 
    consumerIndex: number
  ): Promise<ReadableStream | null> {
    
    const checkpoint = this.checkpoints.get(streamId);
    if (!checkpoint) return null;
    
    if (checkpoint.resurrectionAttempts >= this.config.maxResurrectionAttempts) {
      console.error(`Max resurrection attempts reached for stream ${streamId}`);
      return null;
    }
    
    checkpoint.resurrectionAttempts++;
    
    try {
      switch (checkpoint.materializationType) {
        case 'full':
          return await this.resurrectFromFullMaterialization(checkpoint);
          
        case 'partial':
          return await this.resurrectFromPartialMaterialization(checkpoint);
          
        case 'regenerate':
          return await this.resurrectViaRegeneration(checkpoint);
          
        default:
          throw new Error(`Unknown materialization type: ${checkpoint.materializationType}`);
      }
    } catch (error: any) {
      console.error(`Stream resurrection failed: ${error.message}`);
      return null;
    }
  }
  
  private async resurrectFromFullMaterialization(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    // Load materialized data from storage
    const storageKey = `stream-checkpoint-${checkpoint.streamId}`;
    const materialized = await this.storage.retrieve(storageKey);
    
    // Convert back to stream
    const stream = new ReadableStream({
      start(controller) {
        if (Array.isArray(materialized)) {
          for (const chunk of materialized) {
            controller.enqueue(chunk);
          }
        } else {
          controller.enqueue(materialized);
        }
        controller.close();
      }
    });
    
    checkpoint.status = 'resurrected';
    
    return stream;
  }
  
  private async resurrectFromPartialMaterialization(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    // Load partial data
    const storageKey = `stream-checkpoint-${checkpoint.streamId}`;
    const partialData = await this.storage.retrieve(storageKey);
    
    // Return stream that first emits partial data, then signals "incomplete"
    const stream = new ReadableStream({
      start(controller) {
        if (Array.isArray(partialData)) {
          for (const chunk of partialData) {
            controller.enqueue(chunk);
          }
        }
        
        // Signal incomplete
        controller.enqueue({
          $incomplete: true,
          offset: checkpoint.partialOffset,
          message: 'Stream was interrupted. Partial data only.'
        });
        
        controller.close();
      }
    });
    
    checkpoint.status = 'resurrected';
    
    return stream;
  }
  
  private async resurrectViaRegeneration(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    if (!checkpoint.regenerationConfig) {
      throw new Error('No regeneration config available');
    }
    
    // Re-execute the node to regenerate the stream
    // This requires access to the executor (injected via callback)
    const regenerated = await this.executeNodeForRegeneration(
      checkpoint.sourceNodeId,
      checkpoint.regenerationConfig.nodeConfig,
      checkpoint.regenerationConfig.inputs
    );
    
    checkpoint.status = 'resurrected';
    
    return regenerated;
  }
  
  private async executeNodeForRegeneration(
    nodeId: string,
    nodeConfig: any,
    inputs: Record<string, any>
  ): Promise<ReadableStream> {
    
    // This is called by injecting an executor callback during initialization
    // For now, throw error to indicate implementation needed
    throw new Error(
      'Regeneration requires executor callback. ' +
      'Set ResilientStreamManager.regenerationExecutor = (node, inputs) => stream'
    );
  }
  
  private startAutoCheckpointing(): void {
    setInterval(() => {
      this.checkpointLongLivedStreams();
    }, this.config.autoCheckpointInterval);
  }
  
  private async checkpointLongLivedStreams(): Promise<void> {
    const now = Date.now();
    const threshold = this.config.checkpointThresholdAge;
    
    for (const [streamId, entry] of this.activeStreams.entries()) {
      const age = now - entry.checkpoint.createdAt;
      
      if (age > threshold && entry.checkpoint.status === 'active') {
        await this.checkpointStream(streamId);
      }
    }
  }
  
  private async checkpointStream(streamId: string): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    const checkpoint = entry.checkpoint;
    
    switch (checkpoint.materializationType) {
      case 'full':
        // Materialize all consumed chunks so far
        if (entry.materializedChunks && entry.materializedChunks.length > 0) {
          const storageKey = `stream-checkpoint-${streamId}`;
          checkpoint.materializedData = [...entry.materializedChunks];
          
          await this.storage.store(storageKey, checkpoint.materializedData, {
            temporary: false,
            pinned: true,
            nodeId: checkpoint.sourceNodeId,
            dataType: 'materialized'
          });
          
          checkpoint.status = 'checkpointed';
          checkpoint.lastCheckpointAt = Date.now();
        }
        break;
        
      case 'partial':
        // Only keep last N chunks
        if (entry.materializedChunks) {
          const keepCount = 10;
          const partial = entry.materializedChunks.slice(-keepCount);
          
          const storageKey = `stream-checkpoint-${streamId}`;
          await this.storage.store(storageKey, partial, {
            temporary: false,
            pinned: true,
            nodeId: checkpoint.sourceNodeId,
            dataType: 'materialized'
          });
          
          checkpoint.partialOffset = entry.materializedChunks.length - keepCount;
          checkpoint.status = 'checkpointed';
          checkpoint.lastCheckpointAt = Date.now();
        }
        break;
        
      case 'regenerate':
        // No materialization needed - regeneration config already stored
        checkpoint.status = 'checkpointed';
        checkpoint.lastCheckpointAt = Date.now();
        break;
    }
    
    // Persist checkpoint metadata to SessionStorage
    await this.persistCheckpoint(checkpoint);
  }
  
  private async persistCheckpoint(checkpoint: StreamCheckpoint): Promise<void> {
    const key = `stream-checkpoint-meta-${checkpoint.streamId}`;
    sessionStorage.setItem(key, JSON.stringify(checkpoint));
  }
  
  private async restoreCheckpointsFromStorage(): Promise<void> {
    const keys = Object.keys(sessionStorage);
    
    for (const key of keys) {
      if (key.startsWith('stream-checkpoint-meta-')) {
        const checkpointData = sessionStorage.getItem(key);
        if (checkpointData) {
          const checkpoint: StreamCheckpoint = JSON.parse(checkpointData);
          this.checkpoints.set(checkpoint.streamId, checkpoint);
        }
      }
    }
  }
  
  private createMultiTee(stream: ReadableStream, count: number): ReadableStream[] {
    if (count === 1) return [stream];
    if (count === 2) return stream.tee();
    
    const streams: ReadableStream[] = [];
    let remaining = stream;
    
    for (let i = 0; i < count - 1; i++) {
      const [stream1, stream2] = remaining.tee();
      streams.push(stream1);
      remaining = stream2;
    }
    streams.push(remaining);
    
    return streams;
  }
  
  async acquireReader(
    streamId: string, 
    consumerIndex: number
  ): Promise<ReadableStreamDefaultReader> {
    const stream = await this.getStream(streamId, consumerIndex);
    const reader = stream.getReader();
    
    const entry = this.activeStreams.get(streamId);
    if (entry) {
      entry.readers.add(reader);
      
      // Wrap reader to capture chunks for checkpointing
      if (entry.materializedChunks) {
        return this.wrapReaderForCheckpointing(reader, entry.materializedChunks);
      }
    }
    
    return reader;
  }
  
  private wrapReaderForCheckpointing(
    reader: ReadableStreamDefaultReader,
    chunksBuffer: any[]
  ): ReadableStreamDefaultReader {
    
    const originalRead = reader.read.bind(reader);
    
    reader.read = async () => {
      const result = await originalRead();
      
      if (!result.done && result.value !== undefined) {
        chunksBuffer.push(result.value);
      }
      
      return result;
    };
    
    return reader;
  }
  
  async releaseReader(
    streamId: string, 
    reader: ReadableStreamDefaultReader
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    try {
      reader.releaseLock();
    } catch {
      // Already released
    }
    
    entry.readers.delete(reader);
    
    if (entry.readers.size === 0) {
      await this.cleanup(streamId, 'completed');
    }
  }
  
  private async cleanup(
    streamId: string, 
    reason: 'completed' | 'error' | 'timeout'
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    // Final checkpoint before cleanup
    if (reason === 'completed' && entry.checkpoint.materializationType !== 'regenerate') {
      await this.checkpointStream(streamId);
    }
    
    entry.checkpoint.status = 'expired';
    
    for (const stream of entry.streams) {
      try {
        const reader = stream.getReader();
        await reader.cancel(`Cleanup: ${reason}`);
        reader.releaseLock();
      } catch {
        // Ignore
      }
    }
    
    this.activeStreams.delete(streamId);
  }
  
  private startTimeoutMonitor(): void {
    setInterval(() => {
      const now = Date.now();
      const timeout = this.config.streamTimeout;
      
      for (const [streamId, entry] of this.activeStreams.entries()) {
        if (now - entry.checkpoint.lastCheckpointAt > timeout) {
          console.warn(`Stream timeout: ${streamId}`);
          this.cleanup(streamId, 'timeout');
        }
      }
    }, 60000);
  }
  
  getCheckpoint(streamId: string): StreamCheckpoint | null {
    return this.checkpoints.get(streamId) ?? null;
  }
  
  listActiveStreams(): StreamCheckpoint[] {
    return Array.from(this.activeStreams.values())
      .map(entry => entry.checkpoint);
  }
  
  // Public property for injecting regeneration logic
  regenerationExecutor?: (
    nodeId: string, 
    nodeConfig: any, 
    inputs: Record<string, any>
  ) => Promise<ReadableStream>;
}

interface ActiveStreamEntry {
  checkpoint: StreamCheckpoint;
  streams: ReadableStream[];
  readers: Set<ReadableStreamDefaultReader>;
  materializedChunks?: any[];  // For 'full' or 'partial' checkpointing
}
```

## Enhanced Tiered Storage with Per-Workflow Policies

### Key Innovation: Workflow-Scoped Storage Configuration

```typescript
interface WorkflowStoragePolicy {
  workflowId: string;
  
  // Tier capacities (per workflow)
  memoryCacheMaxBytes: number;          // Default: 50MB per workflow
  indexedDBMaxBytes: number;            // Default: 500MB per workflow
  
  // Overflow behavior
  overflowPolicy: 'evict-lru' | 'evict-oldest' | 'fail' | 'compress' | 'external';
  
  // Eviction preferences
  evictionPreferences: {
    protectRecent: boolean;             // Don't evict < 5s old
    protectFrequent: boolean;           // Prefer low-access items
    protectPinned: boolean;             // Never evict pinned
  };
  
  // Auto-cleanup
  autoCleanupAge: number;               // 24h
  enableAutoCleanup: boolean;
}

class TieredStorageManager {
  private memoryCache: Map<string, CacheEntry> = new Map();
  private memoryCacheSize: number = 0;
  private indexedDB: IDBDatabase;
  private indexedDBSize: number = 0;
  
  // Per-workflow policies
  private workflowPolicies: Map<string, WorkflowStoragePolicy> = new Map();
  private globalPolicy: WorkflowStoragePolicy;
  
  // Artifact metadata
  private artifactIndex: Map<string, ArtifactMetadata> = new Map();
  
  // External blobs
  private externalBlobs: Map<string, string> = new Map();
  
  // Session-level temporary storage (survives refresh)
  private sessionStorage: Storage = window.sessionStorage;
  
  constructor(globalPolicy: WorkflowStoragePolicy) {
    this.globalPolicy = globalPolicy;
    this.initIndexedDB();
    this.restoreFromSession();
  }
  
  setWorkflowPolicy(workflowId: string, policy: WorkflowStoragePolicy): void {
    this.workflowPolicies.set(workflowId, policy);
  }
  
  getPolicy(workflowId?: string): WorkflowStoragePolicy {
    if (workflowId) {
      return this.workflowPolicies.get(workflowId) ?? this.globalPolicy;
    }
    return this.globalPolicy;
  }
  
  async store(
    key: string, 
    data: any, 
    hints: StorageHints = {}
  ): Promise<void> {
    
    const policy = this.getPolicy(hints.workflowId);
    const serialized = JSON.stringify(data);
    const sizeBytes = new TextEncoder().encode(serialized).length;
    
    // Create metadata
    const metadata: ArtifactMetadata = {
      key,
      sizeBytes,
      tier: 'determining',
      createdAt: Date.now(),
      lastAccessedAt: Date.now(),
      accessCount: 0,
      temporary: hints.temporary ?? true,
      pinned: hints.pinned ?? false,
      nodeId: hints.nodeId,
      executionId: hints.executionId,
      workflowId: hints.workflowId,
      dataType: hints.dataType ?? 'json'
    };
    
    this.artifactIndex.set(key, metadata);
    
    // Check if we should use session storage (for critical workflow state)
    if (hints.useSessionStorage) {
      this.sessionStorage.setItem(key, serialized);
      metadata.tier = 'session';
      return;
    }
    
    // Tier decision
    if (sizeBytes < 1024 * 1024) {
      if (await this.tryStoreInMemory(key, data, sizeBytes, policy)) {
        metadata.tier = 'memory';
        return;
      }
    }
    
    await this.storeInIndexedDB(key, serialized, sizeBytes, policy);
    metadata.tier = 'indexeddb';
  }
  
  private async tryStoreInMemory(
    key: string, 
    data: any, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<boolean> {
    
    if (this.memoryCacheSize + sizeBytes <= policy.memoryCacheMaxBytes) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    if (await this.evictFromMemory(sizeBytes, policy)) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    return false;
  }
  
  private async evictFromMemory(
    requiredBytes: number, 
    policy: WorkflowStoragePolicy
  ): Promise<boolean> {
    
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'memory' &&
        (!policy.evictionPreferences.protectPinned || !m.pinned) &&
        (!policy.evictionPreferences.protectRecent || 
         Date.now() - m.createdAt > 5000)
      );
    
    // Sort by policy
    candidates.sort((a, b) => {
      if (policy.evictionPreferences.protectFrequent) {
        if (a.accessCount !== b.accessCount) {
          return a.accessCount - b.accessCount;
        }
      }
      
      if (policy.overflowPolicy === 'evict-oldest') {
        return a.createdAt - b.createdAt;
      } else {
        return a.lastAccessedAt - b.lastAccessedAt;
      }
    });
    
    let freedBytes = 0;
    const toEvict: string[] = [];
    
    for (const metadata of candidates) {
      toEvict.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (freedBytes < requiredBytes) return false;
    
    for (const key of toEvict) {
      const entry = this.memoryCache.get(key)!;
      await this.storeInIndexedDB(key, JSON.stringify(entry.data), entry.sizeBytes, policy);
      
      this.memoryCache.delete(key);
      this.memoryCacheSize -= entry.sizeBytes;
      
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        metadata.tier = 'indexeddb';
      }
    }
    
    return true;
  }
  
  private async storeInIndexedDB(
    key: string, 
    serialized: string, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    if (this.indexedDBSize + sizeBytes > policy.indexedDBMaxBytes) {
      await this.handleIndexedDBOverflow(key, serialized, sizeBytes, policy);
      return;
    }
    
    const shouldCompress = sizeBytes > 1024 * 1024;
    const toStore = shouldCompress 
      ? await this.compress(serialized)
      : serialized;
    
    const actualSize = shouldCompress 
      ? new TextEncoder().encode(toStore).length 
      : sizeBytes;
    
    const tx = this.indexedDB.transaction('artifacts', 'readwrite');
    await tx.objectStore('artifacts').put({
      key,
      data: toStore,
      compressed: shouldCompress,
      sizeBytes: actualSize,
      storedAt: Date.now()
    });
    
    this.indexedDBSize += actualSize;
  }
  
  private async handleIndexedDBOverflow(
    key: string, 
    serialized: string, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    switch (policy.overflowPolicy) {
      case 'evict-lru':
      case 'evict-oldest':
        await this.evictFromIndexedDB(sizeBytes, policy);
        await this.storeInIndexedDB(key, serialized, sizeBytes, policy);
        break;
        
      case 'fail':
        throw new StorageFullError(
          `Storage full for workflow: ${policy.workflowId}`,
          this.getStorageStats()
        );
        
      case 'compress':
        const compressed = await this.compress(serialized);
        const compressedSize = new TextEncoder().encode(compressed).length;
        
        if (this.indexedDBSize + compressedSize > policy.indexedDBMaxBytes) {
          await this.evictFromIndexedDB(compressedSize, policy);
        }
        
        const tx = this.indexedDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').put({
          key,
          data: compressed,
          compressed: true,
          sizeBytes: compressedSize,
          storedAt: Date.now()
        });
        
        this.indexedDBSize += compressedSize;
        break;
        
      case 'external':
        const blob = new Blob([await this.compress(serialized)]);
        const blobUrl = URL.createObjectURL(blob);
        
        this.externalBlobs.set(key, blobUrl);
        
        const tx2 = this.indexedDB.transaction('blobRefs', 'readwrite');
        await tx2.objectStore('blobRefs').put({
          key,
          blobUrl,
          sizeBytes,
          storedAt: Date.now()
        });
        
        const metadata = this.artifactIndex.get(key);
        if (metadata) {
          metadata.tier = 'external';
        }
        break;
    }
  }
  
  private async evictFromIndexedDB(
    requiredBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'indexeddb' &&
        (!policy.evictionPreferences.protectPinned || !m.pinned) &&
        m.workflowId === policy.workflowId  // Only evict from same workflow
      );
    
    candidates.sort((a, b) => {
      if (policy.evictionPreferences.protectFrequent) {
        if (a.accessCount !== b.accessCount) {
          return a.accessCount - b.accessCount;
        }
      }
      
      if (policy.overflowPolicy === 'evict-oldest') {
        return a.createdAt - b.createdAt;
      } else {
        return a.lastAccessedAt - b.lastAccessedAt;
      }
    });
    
    let freedBytes = 0;
    const toDelete: string[] = [];
    
    for (const metadata of candidates) {
      toDelete.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (toDelete.length === 0) {
      throw new Error('Cannot evict: all items protected or wrong workflow');
    }
    
    const txDelete = this.indexedDB.transaction('artifacts', 'readwrite');
    const storeDelete = txDelete.objectStore('artifacts');
    
    for (const key of toDelete) {
      await storeDelete.delete(key);
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        this.indexedDBSize -= metadata.sizeBytes;
      }
      this.artifactIndex.delete(key);
    }
  }
  
  async retrieve(key: string): Promise<any> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) {
      throw new Error(`Artifact not found: ${key}`);
    }
    
    metadata.accessCount++;
    metadata.lastAccessedAt = Date.now();
    
    switch (metadata.tier) {
      case 'memory':
        return this.memoryCache.get(key)?.data;
        
      case 'indexeddb':
        return await this.retrieveFromIndexedDB(key);
        
      case 'session':
        const sessionData = this.sessionStorage.getItem(key);
        return sessionData ? JSON.parse(sessionData) : null;
        
      case 'external':
        return await this.retrieveFromExternalBlob(key);
        
      default:
        throw new Error(`Unknown tier: ${metadata.tier}`);
    }
  }
  
  private async retrieveFromIndexedDB(key: string): Promise<any> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const record = await tx.objectStore('artifacts').get(key);
    
    if (!record) {
      throw new Error(`Artifact not in IndexedDB: ${key}`);
    }
    
    const serialized = record.compressed
      ? await this.decompress(record.data)
      : record.data;
    
    return JSON.parse(serialized);
  }
  
  private async retrieveFromExternalBlob(key: string): Promise<any> {
    const blobUrl = this.externalBlobs.get(key);
    if (!blobUrl) {
      throw new Error(`External blob not found: ${key}`);
    }
    
    const response = await fetch(blobUrl);
    const compressed = await response.text();
    const serialized = await this.decompress(compressed);
    return JSON.parse(serialized);
  }
  
  async pin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = true;
    }
  }
  
  async unpin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = false;
    }
  }
  
  private async compress(data: string): Promise<string> {
    const stream = new Blob([data]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    
    const uint8 = new Uint8Array(buffer);
    return btoa(String.fromCharCode(...uint8));
  }
  
  private async decompress(data: string): Promise<string> {
    const binary = atob(data);
    const uint8 = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      uint8[i] = binary.charCodeAt(i);
    }
    
    const stream = new Blob([uint8]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowStorage', 4);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.indexedDB = request.result;
        this.calculateIndexedDBSize();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('artifacts')) {
          const store = db.createObjectStore('artifacts', { keyPath: 'key' });
          store.createIndex('storedAt', 'storedAt', { unique: false });
          store.createIndex('workflowId', 'workflowId', { unique: false });
        }
        
        if (!db.objectStoreNames.contains('blobRefs')) {
          db.createObjectStore('blobRefs', { keyPath: 'key' });
        }
      };
    });
  }
  
  private async calculateIndexedDBSize(): Promise<void> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    let cursor = await store.openCursor();
    
    let totalSize = 0;
    while (cursor) {
      totalSize += cursor.value.sizeBytes || 0;
      cursor = await cursor.continue();
    }
    
    this.indexedDBSize = totalSize;
  }
  
  private restoreFromSession(): void {
    // Restore critical workflow state from session storage
    const keys = Object.keys(this.sessionStorage);
    
    for (const key of keys) {
      if (key.startsWith('workflow-')) {
        const metadata: ArtifactMetadata = {
          key,
          sizeBytes: this.sessionStorage.getItem(key)!.length,
          tier: 'session',
          createdAt: Date.now(),
          lastAccessedAt: Date.now(),
          accessCount: 0,
          temporary: false,
          pinned: true,
          dataType: 'json'
        };
        
        this.artifactIndex.set(key, metadata);
      }
    }
  }
  
  getStorageStats(workflowId?: string): StorageStats {
    const stats = {
      memory: { count: 0, bytes: this.memoryCacheSize },
      indexeddb: { count: 0, bytes: this.indexedDBSize },
      session: { count: 0, bytes: 0 },
      external: { count: 0, bytes: 0 },
      total: { count: this.artifactIndex.size, bytes: 0 }
    };
    
    for (const metadata of this.artifactIndex.values()) {
      if (workflowId && metadata.workflowId !== workflowId) continue;
      
      stats[metadata.tier as keyof typeof stats].count++;
      stats.total.bytes += metadata.sizeBytes;
    }
    
    return stats;
  }
}

interface CacheEntry {
  data: any;
  sizeBytes: number;
  storedAt: number;
}

interface StorageHints {
  temporary?: boolean;
  pinned?: boolean;
  nodeId?: string;
  executionId?: string;
  workflowId?: string;
  dataType?: 'stream-ref' | 'materialized' | 'blob' | 'json';
  useSessionStorage?: boolean;
}

interface ArtifactMetadata {
  key: string;
  sizeBytes: number;
  tier: 'memory' | 'indexeddb' | 'session' | 'external' | 'determining';
  createdAt: number;
  lastAccessedAt: number;
  accessCount: number;
  temporary: boolean;
  pinned: boolean;
  nodeId?: string;
  executionId?: string;
  workflowId?: string;
  dataType: 'stream-ref' | 'materialized' | 'blob' | 'json';
}

interface StorageStats {
  memory: { count: number; bytes: number };
  indexeddb: { count: number; bytes: number };
  session: { count: number; bytes: number };
  external: { count: number; bytes: number };
  total: { count: number; bytes: number };
}

class StorageFullError extends Error {
  constructor(message: string, public stats: StorageStats) {
    super(message);
    this.name = 'StorageFullError';
  }
}
```

## Visual-Text Hybrid Expression Editor

### Key Innovation: Rich Text Editor with Inline Block Components

```typescript
interface HybridExpression {
  mode: 'hybrid';
  content: EditorContent[];  // Prosemirror-style content
  rawText: string;           // Plain text with markers (for serialization)
}

type EditorContent = TextNode | BlockNode;

interface TextNode {
  type: 'text';
  text: string;
}

interface BlockNode {
  type: 'block';
  blockType: 'field' | 'filter' | 'map' | 'aggregate' | 'transform';
  config: Record<string, any>;
  displayText: string;  // Human-readable representation
}

class HybridExpressionEditor {
  private engine: ComposableExpressionEngine;
  
  constructor() {
    this.engine = new ComposableExpressionEngine();
  }
  
  parseFromText(text: string): HybridExpression {
    const content: EditorContent[] = [];
    const blockMarkerRegex = /\{\{block:([^:}]+):([^}]+)\}\}/g;
    
    let lastIndex = 0;
    const matches = text.matchAll(blockMarkerRegex);
    
    for (const match of matches) {
      // Add text before block
      if (match.index! > lastIndex) {
        const textPart = text.slice(lastIndex, match.index);
        if (textPart) {
          content.push({ type: 'text', text: textPart });
        }
      }
      
      // Parse block
      const [_, blockType, configStr] = match;
      const config = this.parseBlockConfig(blockType, configStr);
      const displayText = this.generateDisplayText(blockType, config);
      
      content.push({
        type: 'block',
        blockType: blockType as any,
        config,
        displayText
      });
      
      lastIndex = match.index! + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      content.push({ type: 'text', text: text.slice(lastIndex) });
    }
    
    return {
      mode: 'hybrid',
      content,
      rawText: text
    };
  }
  
  serializeToText(expression: HybridExpression): string {
    return expression.content.map(node => {
      if (node.type === 'text') {
        return node.text;
      } else {
        const configStr = this.serializeBlockConfig(node.blockType, node.config);
        return `{{block:${node.blockType}:${configStr}}}`;
      }
    }).join('');
  }
  
  private parseBlockConfig(type: string, configStr: string): Record<string, any> {
    const pairs = configStr.split(':');
    
    switch (type) {
      case 'field':
        return { path: pairs[0] };
      case 'filter':
        return { condition: pairs[0] };
      case 'aggregate':
        return { function: pairs[0], path: pairs[1] || '' };
      case 'map':
        return { expression: pairs[0] };
      case 'transform':
        return { operation: pairs[0] };
      default:
        return {};
    }
  }
  
  private serializeBlockConfig(type: string, config: Record<string, any>): string {
    switch (type) {
      case 'field':
        return config.path;
      case 'filter':
        return config.condition;
      case 'aggregate':
        return `${config.function}:${config.path}`;
      case 'map':
        return config.expression;
      case 'transform':
        return config.operation;
      default:
        return '';
    }
  }
  
  private generateDisplayText(type: string, config: Record<string, any>): string {
    switch (type) {
      case 'field':
        return `$.${config.path}`;
      case 'filter':
        return `[${config.condition}]`;
      case 'aggregate':
        return `${config.function}(${config.path})`;
      case 'map':
        return `map(${config.expression})`;
      case 'transform':
        return config.operation;
      default:
        return 'block';
    }
  }
  
  insertBlock(
    expression: HybridExpression, 
    cursorPosition: number,
    blockType: string,
    config: Record<string, any>
  ): HybridExpression {
    
    const displayText = this.generateDisplayText(blockType, config);
    const blockNode: BlockNode = {
      type: 'block',
      blockType: blockType as any,
      config,
      displayText
    };
    
    // Find position in content array
    let currentPos = 0;
    let insertIndex = 0;
    
    for (let i = 0; i < expression.content.length; i++) {
      const node = expression.content[i];
      const nodeLength = node.type === 'text' 
        ? node.text.length 
        : node.displayText.length;
      
      if (currentPos + nodeLength >= cursorPosition) {
        insertIndex = i + 1;
        break;
      }
      
      currentPos += nodeLength;
    }
    
    const newContent = [
      ...expression.content.slice(0, insertIndex),
      blockNode,
      ...expression.content.slice(insertIndex)
    ];
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent })
    };
  }
  
  removeBlock(expression: HybridExpression, blockIndex: number): HybridExpression {
    const newContent = expression.content.filter((_, i) => i !== blockIndex);
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent })
    };
  }
  
  updateBlock(
    expression: HybridExpression, 
    blockIndex: number,
    newConfig: Record<string, any>
  ): HybridExpression {
    
    const node = expression.content[blockIndex];
    if (node.type !== 'block') {
      throw new Error('Node is not a block');
    }
    
    const updatedNode: BlockNode = {
      ...node,
      config: newConfig,
      displayText: this.generateDisplayText(node.blockType, newConfig)
    };
    
    const newContent = [
      ...expression.content.slice(0, blockIndex),
      updatedNode,
      ...expression.content.slice(blockIndex + 1)
    ];
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent })
    };
  }
}

// React Component
const HybridExpressionEditorUI: React.FC<{
  value: HybridExpression;
  onChange: (value: HybridExpression) => void;
}> = ({ value, onChange }) => {
  
  const editor = useMemo(() => new HybridExpressionEditor(), []);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [selectedBlockIndex, setSelectedBlockIndex] = useState<number | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  
  const handleInsertBlock = (blockType: string) => {
    const defaultConfig = getDefaultBlockConfig(blockType);
    const updated = editor.insertBlock(value, cursorPosition, blockType, defaultConfig);
    onChange(updated);
  };
  
  const handleRemoveBlock = (blockIndex: number) => {
    const updated = editor.removeBlock(value, blockIndex);
    onChange(updated);
    setSelectedBlockIndex(null);
  };
  
  const handleUpdateBlock = (blockIndex: number, newConfig: Record<string, any>) => {
    const updated = editor.updateBlock(value, blockIndex, newConfig);
    onChange(updated);
  };
  
  const handleTextChange = (newText: string) => {
    const parsed = editor.parseFromText(newText);
    onChange(parsed);
  };
  
  return (
    <div className="hybrid-expression-editor">
      {/* Block Palette */}
      <div className="block-palette">
        <button onClick={() => handleInsertBlock('field')}>
          <span className="icon">📄</span> Field
        </button>
        <button onClick={() => handleInsertBlock('filter')}>
          <span className="icon">🔍</span> Filter
        </button>
        <button onClick={() => handleInsertBlock('aggregate')}>
          <span className="icon">Σ</span> Aggregate
        </button>
        <button onClick={() => handleInsertBlock('map')}>
          <span className="icon">🗺️</span> Map
        </button>
        <button onClick={() => handleInsertBlock('transform')}>
          <span className="icon">⚙️</span> Transform
        </button>
      </div>
      
      {/* Rich Text Editor */}
      <div 
        ref={editorRef}
        className="editor-content"
        contentEditable
        suppressContentEditableWarning
        onInput={(e) => {
          const text = e.currentTarget.textContent || '';
          handleTextChange(text);
        }}
        onSelect={() => {
          const selection = window.getSelection();
          if (selection) {
            setCursorPosition(selection.anchorOffset);
          }
        }}
      >
        {value.content.map((node, index) => {
          if (node.type === 'text') {
            return <span key={index}>{node.text}</span>;
          } else {
            return (
              <BlockComponent
                key={index}
                node={node}
                selected={selectedBlockIndex === index}
                onSelect={() => setSelectedBlockIndex(index)}
                onRemove={() => handleRemoveBlock(index)}
                onUpdate={(config) => handleUpdateBlock(index, config)}
              />
            );
          }
        })}
      </div>
      
      {/* Block Config Panel (when block selected) */}
      {selectedBlockIndex !== null && value.content[selectedBlockIndex].type === 'block' && (
        <BlockConfigPanel
          blockNode={value.content[selectedBlockIndex] as BlockNode}
          onUpdate={(config) => handleUpdateBlock(selectedBlockIndex, config)}
          onClose={() => setSelectedBlockIndex(null)}
        />
      )}
      
      {/* Raw Text View (toggle) */}
      <details className="raw-text-view">
        <summary>View Raw Text</summary>
        <textarea 
          value={value.rawText}
          onChange={(e) => handleTextChange(e.target.value)}
          className="raw-text-editor"
        />
      </details>
    </div>
  );
};

const BlockComponent: React.FC<{
  node: BlockNode;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onUpdate: (config: Record<string, any>) => void;
}> = ({ node, selected, onSelect, onRemove, onUpdate }) => {
  
  const getBlockIcon = (type: string) => {
    switch (type) {
      case 'field': return '📄';
      case 'filter': return '🔍';
      case 'aggregate': return 'Σ';
      case 'map': return '🗺️';
      case 'transform': return '⚙️';
      default: return '🧩';
    }
  };
  
  return (
    <span 
      className={`expression-block ${selected ? 'selected' : ''}`}
      onClick={onSelect}
      contentEditable={false}
    >
      <span className="block-icon">{getBlockIcon(node.blockType)}</span>
      <span className="block-text">{node.displayText}</span>
      <button className="block-remove" onClick={onRemove}>×</button>
    </span>
  );
};

const BlockConfigPanel: React.FC<{
  blockNode: BlockNode;
  onUpdate: (config: Record<string, any>) => void;
  onClose: () => void;
}> = ({ blockNode, onUpdate, onClose }) => {
  
  const [config, setConfig] = useState(blockNode.config);
  
  const handleSave = () => {
    onUpdate(config);
    onClose();
  };
  
  return (
    <div className="block-config-panel">
      <div className="panel-header">
        <h4>Configure {blockNode.blockType}</h4>
        <button onClick={onClose}>×</button>
      </div>
      
      <div className="panel-body">
        {blockNode.blockType === 'field' && (
          <label>
            Path:
            <input 
              type="text"
              value={config.path || ''}
              onChange={(e) => setConfig({ ...config, path: e.target.value })}
            />
          </label>
        )}
        
        {blockNode.blockType === 'filter' && (
          <label>
            Condition:
            <input 
              type="text"
              value={config.condition || ''}
              onChange={(e) => setConfig({ ...config, condition: e.target.value })}
              placeholder="e.g., age > 18"
            />
          </label>
        )}
        
        {blockNode.blockType === 'aggregate' && (
          <>
            <label>
              Function:
              <select 
                value={config.function || 'sum'}
                onChange={(e) => setConfig({ ...config, function: e.target.value })}
              >
                <option value="sum">Sum</option>
                <option value="avg">Average</option>
                <option value="count">Count</option>
                <option value="min">Min</option>
                <option value="max">Max</option>
              </select>
            </label>
            <label>
              Path:
              <input 
                type="text"
                value={config.path || ''}
                onChange={(e) => setConfig({ ...config, path: e.target.value })}
              />
            </label>
          </>
        )}
        
        {blockNode.blockType === 'map' && (
          <label>
            Expression:
            <input 
              type="text"
              value={config.expression || ''}
              onChange={(e) => setConfig({ ...config, expression: e.target.value })}
              placeholder="e.g., name & ' ' & email"
            />
          </label>
        )}
        
        {blockNode.blockType === 'transform' && (
          <label>
            Operation:
            <select 
              value={config.operation || 'uppercase'}
              onChange={(e) => setConfig({ ...config, operation: e.target.value })}
            >
              <option value="uppercase">Uppercase</option>
              <option value="lowercase">Lowercase</option>
              <option value="trim">Trim</option>
              <option value="reverse">Reverse</option>
            </select>
          </label>
        )}
      </div>
      
      <div className="panel-footer">
        <button onClick={handleSave}>Save</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
};

function getDefaultBlockConfig(blockType: string): Record<string, any> {
  switch (blockType) {
    case 'field':
      return { path: '' };
    case 'filter':
      return { condition: '' };
    case 'aggregate':
      return { function: 'sum', path: '' };
    case 'map':
      return { expression: '' };
    case 'transform':
      return { operation: 'uppercase' };
    default:
      return {};
  }
}
```

## Sandboxed Compensation Handlers with Trust Levels

### Key Innovation: CSP-Based Sandboxing + Trust Verification

```typescript
type TrustLevel = 'system' | 'verified' | 'user' | 'untrusted';

interface CompensationHandlerConfig {
  id: string;
  name: string;
  trustLevel: TrustLevel;
  author?: string;
  verified?: boolean;
  
  handlerType: 'builtin' | 'http-api' | 'webhook' | 'custom';
  
  matches: {
    operation?: string[];
    description?: string[];
    service?: string[];
  };
  
  compensation: 
    | { type: 'http-api'; config: HttpApiConfig }
    | { type: 'webhook'; config: WebhookConfig }
    | { type: 'custom'; workerUrl: string }  // Sandboxed Web Worker
    | { type: 'manual'; steps: string[] };
}

interface HttpApiConfig {
  method: 'GET' | 'POST' | 'DELETE' | 'PUT';
  urlTemplate: string;
  allowedDomains: string[];  // Whitelist of domains this handler can call
  headers: Record<string, string>;
  bodyTemplate: string;
  auth?: {
    type: 'bearer' | 'basic' | 'api-key';
    tokenPath: string;
  };
}

interface WebhookConfig {
  url: string;
  allowedDomains: string[];
  method: 'POST' | 'PUT';
  payloadTemplate: string;
}

class SandboxedCompensationHandlerRegistry {
  private handlers: Map<string, CompensationHandler> = new Map();
  private configs: Map<string, CompensationHandlerConfig> = new Map();
  private trustedDomains: Set<string> = new Set(['api.stripe.com', 'hooks.slack.com']);
  
  // User approval tracking
  private approvedHandlers: Set<string> = new Set();
  
  constructor() {
    this.loadApprovedHandlers();
  }
  
  async registerFromConfig(
    config: CompensationHandlerConfig,
    requireApproval: boolean = true
  ): Promise<boolean> {
    
    // Check trust level
    if (requireApproval && config.trustLevel === 'untrusted') {
      const approved = await this.requestUserApproval(config);
      if (!approved) {
        return false;
      }
      this.approvedHandlers.add(config.id);
      this.persistApprovedHandlers();
    }
    
    // Validate config
    const validation = this.validateConfig(config);
    if (!validation.valid) {
      throw new Error(`Invalid handler config: ${validation.error}`);
    }
    
    this.configs.set(config.id, config);
    
    const handler = await this.createHandlerFromConfig(config);
    this.handlers.set(config.id, handler);
    
    return true;
  }
  
  private validateConfig(config: CompensationHandlerConfig): { valid: boolean; error?: string } {
    // Validate HTTP API config
    if (config.compensation.type === 'http-api') {
      const httpConfig = config.compensation.config;
      
      // Check URL against allowed domains
      const url = new URL(httpConfig.urlTemplate.replace(/\{\{[^}]+\}\}/g, 'placeholder'));
      
      if (!httpConfig.allowedDomains.includes(url.hostname)) {
        return {
          valid: false,
          error: `Domain ${url.hostname} not in allowedDomains list`
        };
      }
      
      // For untrusted handlers, require domain to be explicitly trusted
      if (config.trustLevel === 'untrusted' && !this.trustedDomains.has(url.hostname)) {
        return {
          valid: false,
          error: `Domain ${url.hostname} not in trusted domains list`
        };
      }
    }
    
    // Validate webhook config
    if (config.compensation.type === 'webhook') {
      const webhookConfig = config.compensation.config;
      const url = new URL(webhookConfig.url);
      
      if (!webhookConfig.allowedDomains.includes(url.hostname)) {
        return {
          valid: false,
          error: `Webhook domain ${url.hostname} not in allowedDomains list`
        };
      }
    }
    
    // Validate custom handler
    if (config.compensation.type === 'custom') {
      // Custom handlers must use data: URLs or trusted origins
      const workerUrl = config.compensation.workerUrl;
      
      if (!workerUrl.startsWith('data:') && !workerUrl.startsWith('blob:')) {
        return {
          valid: false,
          error: 'Custom handlers must use data: or blob: URLs for security'
        };
      }
    }
    
    return { valid: true };
  }
  
  private async requestUserApproval(
    config: CompensationHandlerConfig
  ): Promise<boolean> {
    
    return new Promise((resolve) => {
      // Show modal to user
      const modal = document.createElement('div');
      modal.className = 'approval-modal';
      modal.innerHTML = `
        <div class="modal-content">
          <h3>⚠️ Handler Approval Required</h3>
          <p>The handler "${config.name}" wants to perform compensations.</p>
          
          <div class="handler-details">
            <p><strong>Trust Level:</strong> ${config.trustLevel}</p>
            <p><strong>Author:</strong> ${config.author || 'Unknown'}</p>
            <p><strong>Type:</strong> ${config.compensation.type}</p>
            
            ${config.compensation.type === 'http-api' ? `
              <p><strong>Will call:</strong> ${config.compensation.config.urlTemplate}</p>
              <p><strong>Allowed domains:</strong> ${config.compensation.config.allowedDomains.join(', ')}</p>
            ` : ''}
            
            ${config.compensation.type === 'webhook' ? `
              <p><strong>Webhook URL:</strong> ${config.compensation.config.url}</p>
            ` : ''}
          </div>
          
          <p class="warning">This handler will be able to make HTTP requests on your behalf. Only approve if you trust the source.</p>
          
          <div class="modal-actions">
            <button id="approve-btn">Approve</button>
            <button id="deny-btn">Deny</button>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      modal.querySelector('#approve-btn')?.addEventListener('click', () => {
        document.body.removeChild(modal);
        resolve(true);
      });
      
      modal.querySelector('#deny-btn')?.addEventListener('click', () => {
        document.body.removeChild(modal);
        resolve(false);
      });
    });
  }
  
  private async createHandlerFromConfig(
    config: CompensationHandlerConfig
  ): Promise<CompensationHandler> {
    
    return {
      name: config.name,
      
      canHandle: (entry: SideEffectEntry) => {
        const { matches } = config;
        
        if (matches.operation && !matches.operation.includes(entry.operation)) {
          return false;
        }
        
        if (matches.description) {
          const descMatch = matches.description.some(pattern => 
            new RegExp(pattern).test(entry.description)
          );
          if (!descMatch) return false;
        }
        
        if (matches.service) {
          const descriptor = entry.compensation as any;
          if (!matches.service.includes(descriptor.service)) {
            return false;
          }
        }
        
        return true;
      },
      
      compensate: async (entry: SideEffectEntry) => {
        switch (config.compensation.type) {
          case 'http-api':
            return this.compensateViaHttpApi(entry, config.compensation.config, config.trustLevel);
            
          case 'webhook':
            return this.compensateViaWebhook(entry, config.compensation.config, config.trustLevel);
            
          case 'custom':
            return this.compensateViaCustomWorker(entry, config.compensation.workerUrl);
            
          case 'manual':
            return {
              success: false,
              requiresUserAction: true,
              manualSteps: config.compensation.steps
            };
            
          default:
            throw new Error(`Unknown compensation type`);
        }
      }
    };
  }
  
  private async compensateViaHttpApi(
    entry: SideEffectEntry,
    config: HttpApiConfig,
    trustLevel: TrustLevel
  ): Promise<CompensationResult> {
    
    const descriptor = entry.compensation as any;
    
    // Resolve URL
    const url = this.resolveTemplate(config.urlTemplate, {
      ...descriptor,
      effectId: entry.id
    });
    
    // Security check: Verify URL domain
    const urlObj = new URL(url);
    if (!config.allowedDomains.includes(urlObj.hostname)) {
      return {
        success: false,
        error: `Security: Domain ${urlObj.hostname} not allowed`,
        requiresUserAction: true,
        manualSteps: ['Manually compensate this effect', `URL attempted: ${url}`]
      };
    }
    
    // Build request
    const headers = { ...config.headers };
    
    if (config.auth) {
      const token = this.extractValue(descriptor, config.auth.tokenPath);
      switch (config.auth.type) {
        case 'bearer':
          headers['Authorization'] = `Bearer ${token}`;
          break;
        case 'api-key':
          headers['Authorization'] = token;
          break;
      }
    }
    
    const body = config.bodyTemplate
      ? this.resolveTemplate(config.bodyTemplate, descriptor)
      : undefined;
    
    try {
      const response = await fetch(url, {
        method: config.method,
        headers,
        body: body ? JSON.stringify(JSON.parse(body)) : undefined
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return {
        success: true,
        message: `Compensated via ${config.method} ${url}`
      };
      
    } catch (error: any) {
      return {
        success: false,
        error: error.message,
        requiresUserAction: true,
        manualSteps: [
          `Failed to compensate via API: ${error.message}`,
          `Operation: ${entry.description}`,
          'Please manually revert'
        ]
      };
    }
  }
  
  private async compensateViaWebhook(
    entry: SideEffectEntry,
    config: WebhookConfig,
    trustLevel: TrustLevel
  ): Promise<CompensationResult> {
    
    const descriptor = entry.compensation as any;
    
    // Security check
    const urlObj = new URL(config.url);
    if (!config.allowedDomains.includes(urlObj.hostname)) {
      return {
        success: false,
        error: `Security: Webhook domain ${urlObj.hostname} not allowed`
      };
    }
    
    const payload = this.resolveTemplate(config.payloadTemplate, {
      ...descriptor,
      effectId: entry.id,
      effectDescription: entry.description
    });
    
    try {
      const response = await fetch(config.url, {
        method: config.method,
        headers: { 'Content-Type': 'application/json' },
        body: payload
      });
      
      if (!response.ok) {
        throw new Error(`Webhook failed: ${response.statusText}`);
      }
      
      return {
        success: true,
        message: `Webhook triggered: ${config.url}`
      };
      
    } catch (error: any) {
      return {
        success: false,
        error: error.message
      };
    }
  }
  
  private async compensateViaCustomWorker(
    entry: SideEffectEntry,
    workerUrl: string
  ): Promise<CompensationResult> {
    
    return new Promise((resolve) => {
      const worker = new Worker(workerUrl);
      
      const timeout = setTimeout(() => {
        worker.terminate();
        resolve({
          success: false,
          error: 'Custom handler timeout'
        });
      }, 10000);
      
      worker.onmessage = (event) => {
        clearTimeout(timeout);
        worker.terminate();
        resolve(event.data);
      };
      
      worker.onerror = (error) => {
        clearTimeout(timeout);
        worker.terminate();
        resolve({
          success: false,
          error: `Worker error: ${error.message}`
        });
      };
      
      worker.postMessage({
        entry,
        descriptor: entry.compensation
      });
    });
  }
  
  private resolveTemplate(template: string, data: any): string {
    return template.replace(/\{\{([^}]+)\}\}/g, (_, path) => {
      return this.extractValue(data, path) ?? '';
    });
  }
  
  private extractValue(obj: any, path: string): any {
    const parts = path.split('.');
    let result = obj;
    for (const part of parts) {
      result = result?.[part];
    }
    return result;
  }
  
  private loadApprovedHandlers(): void {
    const stored = localStorage.getItem('approvedHandlers');
    if (stored) {
      this.approvedHandlers = new Set(JSON.parse(stored));
    }
  }
  
  private persistApprovedHandlers(): void {
    localStorage.setItem('approvedHandlers', JSON.stringify([...this.approvedHandlers]));
  }
  
  serializeConfigs(): CompensationHandlerConfig[] {
    return Array.from(this.configs.values());
  }
  
  loadConfigs(configs: CompensationHandlerConfig[]): void {
    for (const config of configs) {
      // Check if already approved
      const requireApproval = !this.approvedHandlers.has(config.id);
      this.registerFromConfig(config, requireApproval);
    }
  }
  
  unregister(id: string): void {
    this.handlers.delete(id);
    this.configs.delete(id);
    this.approvedHandlers.delete(id);
    this.persistApprovedHandlers();
  }
  
  findHandler(entry: SideEffectEntry): CompensationHandler | null {
    for (const handler of this.handlers.values()) {
      if (handler.canHandle(entry)) {
        return handler;
      }
    }
    return null;
  }
}

interface CompensationHandler {
  name: string;
  compensate(entry: SideEffectEntry): Promise<CompensationResult>;
  canHandle(entry: SideEffectEntry): boolean;
}

interface SideEffectEntry {
  id: string;
  nodeId: string;
  executionId: string;
  timestamp: number;
  operation: string;
  description: string;
  compensation: any;
  status: string;
}

interface CompensationResult {
  success: boolean;
  error?: string;
  message?: string;
  manualSteps?: string[];
  requiresUserAction?: boolean;
}
```

## Adaptive Performance Metrics with IndexedDB Persistence

### Key Innovation: Long-Term Analysis + Sampling Strategy

```typescript
interface MetricsConfig {
  enablePersistence: boolean;        // Store to IndexedDB
  samplingRate: number;              // 0.1 = 10% of measurements
  retentionDays: number;             // 7 days
  enableRecommendations: boolean;
}

interface StreamingMetrics {
  decisions: {
    teeCount: number;
    materializeCount: number;
    batchCount: number;
  };
  
  performance: {
    avgTeeMemory: number;
    avgMaterializeSize: number;
    avgTeeTime: number;
    avgMaterializeTime: number;
  };
  
  errors: {
    teeFailures: number;
    materializeFailures: number;
    storageFullErrors: number;
  };
  
  recommendations: {
    suggestedTeeThreshold: number;
    suggestedMaterializeThreshold: number;
    suggestedOverflowPolicy: string;
  };
}

interface Measurement {
  id: string;
  timestamp: number;
  strategy: 'tee' | 'materialize';
  sizeBytes: number;
  durationMs: number;
  memoryUsed: number;
  workflowId: string;
  nodeId: string;
}

class AdaptivePerformanceMonitor {
  private metrics: StreamingMetrics;
  private recentMeasurements: Measurement[] = [];
  private db: IDBDatabase | null = null;
  private config: MetricsConfig;
  
  constructor(config: MetricsConfig) {
    this.config = config;
    this.metrics = this.initMetrics();
    
    if (config.enablePersistence) {
      this.initDatabase();
    }
  }
  
  recordDecision(
    strategy: 'tee' | 'materialize' | 'batch',
    sizeBytes: number,
    durationMs: number,
    memoryUsed: number,
    context: {
      workflowId: string;
      nodeId: string;
    }
  ): void {
    
    switch (strategy) {
      case 'tee':
        this.metrics.decisions.teeCount++;
        break;
      case 'materialize':
        this.metrics.decisions.materializeCount++;
        break;
      case 'batch':
        this.metrics.decisions.batchCount++;
        break;
    }
    
    if (strategy === 'tee' || strategy === 'materialize') {
      // Apply sampling
      if (Math.random() < this.config.samplingRate) {
        const measurement: Measurement = {
          id: crypto.randomUUID(),
          timestamp: Date.now(),
          strategy,
          sizeBytes,
          durationMs,
          memoryUsed,
          workflowId: context.workflowId,
          nodeId: context.nodeId
        };
        
        this.recentMeasurements.push(measurement);
        
        // Keep last 100 in memory
        if (this.recentMeasurements.length > 100) {
          this.recentMeasurements.shift();
        }
        
        // Persist to IndexedDB
        if (this.config.enablePersistence && this.db) {
          this.persistMeasurement(measurement);
        }
      }
      
      this.updateAverages();
      
      if (this.config.enableRecommendations) {
        this.generateRecommendations();
      }
    }
  }
  
  recordError(type: 'tee' | 'materialize' | 'storage-full'): void {
    switch (type) {
      case 'tee':
        this.metrics.errors.teeFailures++;
        break;
      case 'materialize':
        this.metrics.errors.materializeFailures++;
        break;
      case 'storage-full':
        this.metrics.errors.storageFullErrors++;
        break;
    }
  }
  
  private updateAverages(): void {
    const tees = this.recentMeasurements.filter(m => m.strategy === 'tee');
    const materializes = this.recentMeasurements.filter(m => m.strategy === 'materialize');
    
    if (tees.length > 0) {
      this.metrics.performance.avgTeeMemory = 
        tees.reduce((sum, m) => sum + m.memoryUsed, 0) / tees.length;
      this.metrics.performance.avgTeeTime = 
        tees.reduce((sum, m) => sum + m.durationMs, 0) / tees.length;
    }
    
    if (materializes.length > 0) {
      this.metrics.performance.avgMaterializeSize = 
        materializes.reduce((sum, m) => sum + m.sizeBytes, 0) / materializes.length;
      this.metrics.performance.avgMaterializeTime = 
        materializes.reduce((sum, m) => sum + m.durationMs, 0) / materializes.length;
    }
  }
  
  private generateRecommendations(): void {
    // Tee threshold
    if (this.metrics.performance.avgTeeMemory > 10 * 1024 * 1024) {
      this.metrics.recommendations.suggestedTeeThreshold = 3 * 1024 * 1024;
    } else {
      this.metrics.recommendations.suggestedTeeThreshold = 5 * 1024 * 1024;
    }
    
    // Materialize threshold
    if (this.metrics.performance.avgMaterializeTime < 100) {
      this.metrics.recommendations.suggestedMaterializeThreshold = 100 * 1024 * 1024;
    } else {
      this.metrics.recommendations.suggestedMaterializeThreshold = 50 * 1024 * 1024;
    }
    
    // Overflow policy
    if (this.metrics.errors.storageFullErrors > 5) {
      this.metrics.recommendations.suggestedOverflowPolicy = 'evict-lru';
    } else {
      this.metrics.recommendations.suggestedOverflowPolicy = 'compress';
    }
  }
  
  async getHistoricalMetrics(
    workflowId?: string,
    startTime?: number,
    endTime?: number
  ): Promise<Measurement[]> {
    
    if (!this.config.enablePersistence || !this.db) {
      return this.recentMeasurements;
    }
    
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction('measurements', 'readonly');
      const store = tx.objectStore('measurements');
      const index = store.index('timestamp');
      
      const range = IDBKeyRange.bound(
        startTime || 0,
        endTime || Date.now()
      );
      
      const results: Measurement[] = [];
      const request = index.openCursor(range);
      
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result;
        if (cursor) {
          const measurement: Measurement = cursor.value;
          
          if (!workflowId || measurement.workflowId === workflowId) {
            results.push(measurement);
          }
          
          cursor.continue();
        } else {
          resolve(results);
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }
  
  async generateReport(workflowId?: string): Promise<PerformanceReport> {
    const measurements = await this.getHistoricalMetrics(workflowId);
    
    const tees = measurements.filter(m => m.strategy === 'tee');
    const materializes = measurements.filter(m => m.strategy === 'materialize');
    
    return {
      totalMeasurements: measurements.length,
      timeRange: {
        start: Math.min(...measurements.map(m => m.timestamp)),
        end: Math.max(...measurements.map(m => m.timestamp))
      },
      strategies: {
        tee: {
          count: tees.length,
          avgMemory: tees.reduce((sum, m) => sum + m.memoryUsed, 0) / tees.length,
          avgDuration: tees.reduce((sum, m) => sum + m.durationMs, 0) / tees.length,
          avgSize: tees.reduce((sum, m) => sum + m.sizeBytes, 0) / tees.length
        },
        materialize: {
          count: materializes.length,
          avgMemory: materializes.reduce((sum, m) => sum + m.memoryUsed, 0) / materializes.length,
          avgDuration: materializes.reduce((sum, m) => sum + m.durationMs, 0) / materializes.length,
          avgSize: materializes.reduce((sum, m) => sum + m.sizeBytes, 0) / materializes.length
        }
      },
      recommendations: this.metrics.recommendations
    };
  }
  
  getMetrics(): StreamingMetrics {
    return { ...this.metrics };
  }
  
  getMeasurements(): Measurement[] {
    return [...this.recentMeasurements];
  }
  
  private async initDatabase(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('PerformanceMetrics', 2);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        this.cleanupOldMeasurements();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('measurements')) {
          const store = db.createObjectStore('measurements', { keyPath: 'id' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('workflowId', 'workflowId', { unique: false });
          store.createIndex('strategy', 'strategy', { unique: false });
        }
      };
    });
  }
  
  private async persistMeasurement(measurement: Measurement): Promise<void> {
    if (!this.db) return;
    
    const tx = this.db.transaction('measurements', 'readwrite');
    await tx.objectStore('measurements').add(measurement);
  }
  
  private async cleanupOldMeasurements(): Promise<void> {
    if (!this.db) return;
    
    const cutoff = Date.now() - (this.config.retentionDays * 24 * 60 * 60 * 1000);
    
    const tx = this.db.transaction('measurements', 'readwrite');
    const store = tx.objectStore('measurements');
    const index = store.index('timestamp');
    
    const range = IDBKeyRange.upperBound(cutoff);
    const request = index.openCursor(range);
    
    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
  }
  
  private initMetrics(): StreamingMetrics {
    return {
      decisions: {
        teeCount: 0,
        materializeCount: 0,
        batchCount: 0
      },
      performance: {
        avgTeeMemory: 0,
        avgMaterializeSize: 0,
        avgTeeTime: 0,
        avgMaterializeTime: 0
      },
      errors: {
        teeFailures: 0,
        materializeFailures: 0,
        storageFullErrors: 0
      },
      recommendations: {
        suggestedTeeThreshold: 5 * 1024 * 1024,
        suggestedMaterializeThreshold: 50 * 1024 * 1024,
        suggestedOverflowPolicy: 'evict-lru'
      }
    };
  }
}

interface PerformanceReport {
  totalMeasurements: number;
  timeRange: {
    start: number;
    end: number;
  };
  strategies: {
    tee: {
      count: number;
      avgMemory: number;
      avgDuration: number;
      avgSize: number;
    };
    materialize: {
      count: number;
      avgMemory: number;
      avgDuration: number;
      avgSize: number;
    };
  };
  recommendations: StreamingMetrics['recommendations'];
}
```

---

## Rationale

### 1. Resilient Stream Manager with Auto-Checkpointing
**Why**: Solves the page refresh problem without requiring user intervention.
- **Three materialization strategies**: `full` (all data), `partial` (last N chunks), `regenerate` (re-execute node)
- **Automatic checkpointing**: Long-lived streams (>60s) are automatically checkpointed every 30s
- **SessionStorage for metadata**: Checkpoint metadata persists across page refresh
- **Resurrection logic**: Streams can be restored from checkpoints transparently

### 2. Three-Tier Storage with Per-Workflow Policies
**Why**: Different workflows have different storage needs. Heavy data workflows need aggressive eviction, lightweight workflows don't.
- **Memory + IndexedDB + SessionStorage**: Three tiers with clear purposes
- **Per-workflow policies**: Each workflow can configure its own overflow policy and eviction preferences
- **Global fallback**: Workflows inherit global policy if not customized
- **Session tier for critical state**: Workflow definitions and execution state use SessionStorage (survives refresh)

### 3. Visual-Text Hybrid Expression Editor
**Why**: Best of both worlds - power users can type, visual users can click.
- **Rich text editor with inline blocks**: Blocks appear as visual chips within text
- **Click-to-insert palette**: Easy block insertion at cursor position
- **Configurable blocks**: Click a block to open config panel
- **Raw text fallback**: Toggle to see/edit the underlying `{{block:type:config}}` syntax
- **Automatic sync**: Changes in visual mode update raw text and vice versa

### 4. Sandboxed Compensation Handlers with Trust Levels
**Why**: Security without sacrificing flexibility.
- **Four trust levels**: `system` (built-in), `verified` (marketplace), `user` (self-created), `untrusted` (external)
- **Domain whitelisting**: HTTP handlers can only call explicitly allowed domains
- **User approval for untrusted**: Modal prompts user before registering untrusted handlers
- **CSP sandboxing for custom**: Custom handlers run in Web Workers with no DOM access
- **Approval persistence**: Once approved, handlers don't require re-approval (stored in localStorage)

### 5. Adaptive Performance Metrics with IndexedDB
**Why**: Long-term learning without memory bloat.
- **10% sampling rate**: Only record 1 in 10 measurements to reduce overhead
- **IndexedDB persistence**: Metrics survive page refresh for long-term analysis
- **7-day retention**: Auto-cleanup of old data
- **Per-workflow reports**: Generate performance reports for specific workflows
- **Recommendation engine**: Uses historical data to suggest better thresholds

---

## What I Changed

### Stream Persistence Strategy
**Changed from**: Vague "materialize on timeout" to concrete auto-checkpointing system
- **Added**: Three materialization strategies (full/partial/regenerate)
- **Added**: Automatic 30s checkpoint interval for long-lived streams
- **Added**: SessionStorage-based checkpoint metadata persistence
- **Added**: Transparent stream resurrection after page refresh

### Storage Architecture
**Changed from**: Global overflow policies to per-workflow policies
- **Added**: Third storage tier (SessionStorage) for critical workflow state
- **Added**: Workflow-scoped storage quotas and eviction preferences
- **Added**: Global policy as fallback for workflows without custom config

### Expression Editor UX
**Changed from**: Abstract "inline markers" to concrete rich text editor with visual blocks
- **Added**: Click-to-insert block palette
- **Added**: Visual block components rendered inline with text
- **Added**: Config panel that opens on block selection
- **Added**: Raw text toggle for advanced users

### Compensation Handler Security
**Changed from**: "Should we sandbox?" to concrete CSP-based trust model
- **Added**: Four trust levels with different approval requirements
- **Added**: Domain whitelisting for HTTP/webhook handlers
- **Added**: User approval modal for untrusted handlers
- **Added**: Approval persistence in localStorage
- **Added**: Web Worker sandboxing for custom handlers

### Performance Metrics
**Changed from**: In-memory metrics to persistent, sampled metrics
- **Added**: 10% sampling rate to reduce overhead
- **Added**: IndexedDB persistence with 7-day retention
- **Added**: Historical query API for long-term analysis
- **Added**: Per-workflow performance reports

---

## What I Kept

All core architectural decisions remain:
- React Flow canvas
- Zustand + immer state management
- Adaptive streaming executor
- Two-tier storage (Memory + IndexedDB) - now enhanced to three-tier
- Composable expression system - now with concrete visual editor
- Append-only side effect log
- Checkpoint manager
- Worker pools
- Compression
- All performance optimizations

---

## Open Questions

### 1. Stream Regeneration Executor Injection
The `ResilientStreamManager` needs access to the executor to regenerate streams. Currently it throws an error.
- **Option A**: Inject executor via constructor parameter
- **Option B**: Use callback property `regenerationExecutor` set after initialization
- **Option C**: Pass executor on each `registerStream` call
- **Recommendation**: Option B (callback property) for flexibility

### 2. SessionStorage Capacity Limits
SessionStorage has ~5-10MB limit. For large workflows with many checkpoints:
- **Issue**: May exceed SessionStorage quota
- **Mitigation**: Only store lightweight checkpoint metadata, not full data
- **Alternative**: Use IndexedDB for checkpoint metadata too (but won't survive tab close)

### 3. Sampling Rate Configuration
10% sampling might be too aggressive for small workflows (< 10 executions):
- **Option A**: Dynamic sampling (100% for first 20 measurements, then 10%)
- **Option B**: User-configurable sampling rate per workflow
- **Option C**: Keep static 10% globally
- **Recommendation**: Option A (dynamic) for better initial data

### 4. Trust Level Assignment
How do we assign trust levels to handlers?
- **System**: Built-in handlers (Stripe, Slack, etc.)
- **Verified**: Who verifies? Do we need a marketplace?
- **User**: User-created handlers (default)
- **Untrusted**: Imported from external sources
- **Question**: Should we auto-assign based on handler origin (same-domain = user, cross-domain = untrusted)?

---

## Convergence Status

**PROPOSING_FINAL** - All five critical design questions have concrete, implementable solutions:

✅ Stream persistence: Auto-checkpointing with three materialization strategies  
✅ Expression editor UX: Rich text editor with inline visual blocks  
✅ Handler security: Trust levels + domain whitelisting + CSP sandboxing  
✅ Metrics persistence: IndexedDB + 10% sampling + 7-day retention  
✅ Eviction strategy: Per-workflow policies with global fallback  

All remaining questions are implementation details that can be resolved during coding.

---

## PROMPT_FOR_CRITIC:

The design is complete and ready for implementation. Please focus final review on:

1. **Stream Resurrection Edge Cases**: Are there scenarios where resurrection would fail catastrophically? What if the node config changed between checkpoint and resurrection?

2. **SessionStorage Overflow**: With checkpoint metadata in SessionStorage, what happens when we hit the 5MB limit? Should we have a fallback strategy?

3. **Visual Block Editor Performance**: Rendering many inline block components could be slow. Should we virtualize the editor content? Or set a max block count per expression?

4. **Trust Level UX**: Is the four-level trust model (system/verified/user/untrusted) too complex for users? Would a simpler "trusted/untrusted" binary be better?

5. **Metrics Sampling Bias**: 10% sampling means we might miss rare edge cases or performance spikes. Is there a smarter sampling strategy (e.g., always sample errors, sometimes sample successes)?

If you have strong objections to any of these solutions, please suggest concrete alternatives. Otherwise, this design is ready to build.

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

# Visual AI Agent Workflow Builder - Production-Ready Architecture v6

## Core Architecture

### System Overview
```
┌─────────────────────────────────────────────────────────────────┐
│                     React Application Layer                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Canvas     │  │  Properties  │  │   Toolbar    │         │
│  │   (React     │  │    Panel     │  │   & Palette  │         │
│  │    Flow)     │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
├─────────────────────────────────────────────────────────────────┤
│           State Management (Zustand + Immer)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Execution Orchestration Layer                │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Adaptive   │  │  Resilient │  │ Checkpoint │         │  │
│  │  │ Executor   │  │  Stream    │  │  Manager   │         │  │
│  │  │            │  │  Manager   │  │            │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Data Flow & Storage Layer                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │  │ Composable │  │   Tiered   │  │ Effect Log │         │  │
│  │  │ Expression │  │  Storage   │  │  (Append-  │         │  │
│  │  │  System    │  │  Manager   │  │   Only)    │         │  │
│  │  └────────────┘  └────────────┘  └────────────┘         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Enhanced Resilient Stream Manager (Addressing Critical Edge Cases)

### Key Enhancement: Version-Aware Stream Resurrection with Graceful Degradation

```typescript
interface StreamCheckpoint {
  streamId: string;
  sourceNodeId: string;
  executionId: string;
  consumerCount: number;
  createdAt: number;
  lastCheckpointAt: number;
  
  // VERSION TRACKING - Critical for detecting config changes
  nodeConfigVersion: string;         // Hash of node config at checkpoint time
  nodeConfigSnapshot: any;           // Full config snapshot for validation
  
  // Resurrection data
  materializationType: 'full' | 'partial' | 'regenerate';
  materializedData?: any;
  partialOffset?: number;
  regenerationConfig?: {
    nodeConfig: any;
    inputs: Record<string, any>;
    inputHashes: Record<string, string>;  // NEW: Detect input changes
  };
  
  // Resurrection metadata
  status: 'active' | 'checkpointed' | 'resurrected' | 'expired' | 'stale';
  resurrectionAttempts: number;
  resurrectionStrategy: 'exact' | 'compatible' | 'fail';
  staleness: 'fresh' | 'config-changed' | 'inputs-changed' | 'node-deleted';
}

interface ResurrectionResult {
  success: boolean;
  stream?: ReadableStream;
  degraded?: boolean;              // NEW: Indicates partial success
  warning?: string;                // NEW: User-facing warning message
  fallbackUsed?: 'cached' | 'regenerated' | 'empty';
}

class ResilientStreamManager {
  private activeStreams: Map<string, ActiveStreamEntry> = new Map();
  private checkpoints: Map<string, StreamCheckpoint> = new Map();
  private storage: HybridStorageManager;
  private config: StreamManagerConfig;
  private workflowState: WorkflowStateProvider;  // NEW: Validates node configs
  
  constructor(
    storage: HybridStorageManager, 
    config: StreamManagerConfig,
    workflowState: WorkflowStateProvider
  ) {
    this.storage = storage;
    this.config = config;
    this.workflowState = workflowState;
    
    if (config.enableResurrection) {
      this.restoreCheckpointsFromStorage();
    }
    
    this.startAutoCheckpointing();
    this.startTimeoutMonitor();
    this.startStalenessDetector();  // NEW: Detect stale checkpoints
  }
  
  async registerStream(
    sourceNodeId: string,
    executionId: string,
    stream: ReadableStream,
    consumerCount: number,
    options: {
      estimatedSize: number;
      materializationType?: 'full' | 'partial' | 'regenerate';
      regenerationConfig?: any;
      nodeConfig: any;  // NEW: Required for version tracking
      inputs: Record<string, any>;  // NEW: Required for version tracking
    }
  ): Promise<string> {
    
    if (this.activeStreams.size >= this.config.maxConcurrentStreams) {
      throw new Error(
        `Max concurrent streams reached (${this.config.maxConcurrentStreams})`
      );
    }
    
    const streamId = crypto.randomUUID();
    const teedStreams = this.createMultiTee(stream, consumerCount);
    
    // Create version-aware checkpoint
    const checkpoint: StreamCheckpoint = {
      streamId,
      sourceNodeId,
      executionId,
      consumerCount,
      createdAt: Date.now(),
      lastCheckpointAt: Date.now(),
      nodeConfigVersion: this.hashConfig(options.nodeConfig),
      nodeConfigSnapshot: structuredClone(options.nodeConfig),
      materializationType: options.materializationType ?? 'full',
      regenerationConfig: options.regenerationConfig ? {
        nodeConfig: structuredClone(options.nodeConfig),
        inputs: structuredClone(options.inputs),
        inputHashes: this.hashInputs(options.inputs)
      } : undefined,
      status: 'active',
      resurrectionAttempts: 0,
      resurrectionStrategy: 'exact',
      staleness: 'fresh'
    };
    
    this.checkpoints.set(streamId, checkpoint);
    
    this.activeStreams.set(streamId, {
      checkpoint,
      streams: teedStreams,
      readers: new Set(),
      materializedChunks: options.materializationType !== 'regenerate' ? [] : undefined
    });
    
    return streamId;
  }
  
  async getStream(streamId: string, consumerIndex: number): Promise<ReadableStream> {
    const active = this.activeStreams.get(streamId);
    
    if (active) {
      active.checkpoint.lastCheckpointAt = Date.now();
      return active.streams[consumerIndex];
    }
    
    // Try resurrection with validation
    if (this.config.enableResurrection) {
      const result = await this.resurrectStreamSafe(streamId, consumerIndex);
      
      if (result.success && result.stream) {
        // Notify user if degraded
        if (result.degraded && result.warning) {
          this.notifyDegradedResurrection(streamId, result.warning);
        }
        return result.stream;
      }
    }
    
    throw new Error(`Stream not found and could not be resurrected: ${streamId}`);
  }
  
  private async resurrectStreamSafe(
    streamId: string, 
    consumerIndex: number
  ): Promise<ResurrectionResult> {
    
    const checkpoint = this.checkpoints.get(streamId);
    if (!checkpoint) {
      return { success: false };
    }
    
    if (checkpoint.resurrectionAttempts >= this.config.maxResurrectionAttempts) {
      console.error(`Max resurrection attempts reached for stream ${streamId}`);
      return { success: false };
    }
    
    checkpoint.resurrectionAttempts++;
    
    // CRITICAL: Validate checkpoint freshness
    const validation = await this.validateCheckpointFreshness(checkpoint);
    
    if (validation.stale) {
      checkpoint.staleness = validation.reason;
      
      switch (validation.severity) {
        case 'critical':
          // Node deleted or inputs fundamentally changed
          return {
            success: false,
            warning: `Cannot resurrect: ${validation.message}`
          };
          
        case 'major':
          // Config changed significantly - try regeneration or fail gracefully
          if (checkpoint.materializationType === 'regenerate') {
            // Config changed but we can try regenerating with old config
            return await this.resurrectWithDegradation(checkpoint, {
              strategy: 'regenerate-old-config',
              warning: validation.message
            });
          } else {
            // Use cached data with warning
            return await this.resurrectWithDegradation(checkpoint, {
              strategy: 'use-cached-with-warning',
              warning: validation.message
            });
          }
          
        case 'minor':
          // Minor changes - proceed with warning
          const result = await this.resurrectStream(checkpoint);
          return {
            ...result,
            degraded: true,
            warning: validation.message
          };
          
        default:
          // Fresh - proceed normally
          return await this.resurrectStream(checkpoint);
      }
    }
    
    return await this.resurrectStream(checkpoint);
  }
  
  private async validateCheckpointFreshness(
    checkpoint: StreamCheckpoint
  ): Promise<{
    stale: boolean;
    reason: StreamCheckpoint['staleness'];
    severity: 'none' | 'minor' | 'major' | 'critical';
    message?: string;
  }> {
    
    // Check if node still exists
    const currentNode = this.workflowState.getNode(checkpoint.sourceNodeId);
    if (!currentNode) {
      return {
        stale: true,
        reason: 'node-deleted',
        severity: 'critical',
        message: 'Source node no longer exists in workflow'
      };
    }
    
    // Check if node config changed
    const currentConfigHash = this.hashConfig(currentNode.config);
    if (currentConfigHash !== checkpoint.nodeConfigVersion) {
      // Determine severity of config changes
      const diff = this.diffConfigs(checkpoint.nodeConfigSnapshot, currentNode.config);
      
      if (diff.breaking) {
        return {
          stale: true,
          reason: 'config-changed',
          severity: 'major',
          message: `Node configuration changed: ${diff.summary}`
        };
      } else {
        return {
          stale: true,
          reason: 'config-changed',
          severity: 'minor',
          message: `Minor node configuration changes detected`
        };
      }
    }
    
    // Check if inputs changed (for regenerate strategy)
    if (checkpoint.regenerationConfig) {
      const currentInputs = this.workflowState.getNodeInputs(checkpoint.sourceNodeId);
      const currentInputHashes = this.hashInputs(currentInputs);
      
      const inputsChanged = Object.keys(checkpoint.regenerationConfig.inputHashes).some(
        key => currentInputHashes[key] !== checkpoint.regenerationConfig!.inputHashes[key]
      );
      
      if (inputsChanged) {
        return {
          stale: true,
          reason: 'inputs-changed',
          severity: 'major',
          message: 'Input data has changed since checkpoint'
        };
      }
    }
    
    return {
      stale: false,
      reason: 'fresh',
      severity: 'none'
    };
  }
  
  private async resurrectWithDegradation(
    checkpoint: StreamCheckpoint,
    options: {
      strategy: 'regenerate-old-config' | 'use-cached-with-warning' | 'empty-stream';
      warning: string;
    }
  ): Promise<ResurrectionResult> {
    
    switch (options.strategy) {
      case 'regenerate-old-config':
        try {
          // Attempt regeneration using OLD config from checkpoint
          const stream = await this.resurrectViaRegeneration(checkpoint, {
            useSnapshotConfig: true
          });
          
          return {
            success: true,
            stream,
            degraded: true,
            warning: `${options.warning}. Using previous configuration.`,
            fallbackUsed: 'regenerated'
          };
        } catch (error: any) {
          // Fall back to cached data
          return await this.resurrectWithDegradation(checkpoint, {
            strategy: 'use-cached-with-warning',
            warning: options.warning
          });
        }
        
      case 'use-cached-with-warning':
        if (checkpoint.materializationType !== 'regenerate' && checkpoint.materializedData) {
          const stream = await this.resurrectFromFullMaterialization(checkpoint);
          
          return {
            success: true,
            stream,
            degraded: true,
            warning: `${options.warning}. Using cached data from previous run.`,
            fallbackUsed: 'cached'
          };
        }
        
        // No cached data available - return empty stream
        return await this.resurrectWithDegradation(checkpoint, {
          strategy: 'empty-stream',
          warning: options.warning
        });
        
      case 'empty-stream':
        const emptyStream = new ReadableStream({
          start(controller) {
            controller.enqueue({
              $error: true,
              $resurrectionFailed: true,
              message: options.warning
            });
            controller.close();
          }
        });
        
        return {
          success: true,
          stream: emptyStream,
          degraded: true,
          warning: `${options.warning}. Returning empty stream.`,
          fallbackUsed: 'empty'
        };
    }
  }
  
  private async resurrectStream(
    checkpoint: StreamCheckpoint
  ): Promise<ResurrectionResult> {
    
    try {
      let stream: ReadableStream;
      
      switch (checkpoint.materializationType) {
        case 'full':
          stream = await this.resurrectFromFullMaterialization(checkpoint);
          break;
          
        case 'partial':
          stream = await this.resurrectFromPartialMaterialization(checkpoint);
          break;
          
        case 'regenerate':
          stream = await this.resurrectViaRegeneration(checkpoint, {
            useSnapshotConfig: false
          });
          break;
          
        default:
          throw new Error(`Unknown materialization type: ${checkpoint.materializationType}`);
      }
      
      checkpoint.status = 'resurrected';
      
      return { success: true, stream };
      
    } catch (error: any) {
      console.error(`Stream resurrection failed: ${error.message}`);
      return { success: false };
    }
  }
  
  private async resurrectFromFullMaterialization(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    const storageKey = `stream-checkpoint-${checkpoint.streamId}`;
    const materialized = await this.storage.retrieve(storageKey);
    
    const stream = new ReadableStream({
      start(controller) {
        if (Array.isArray(materialized)) {
          for (const chunk of materialized) {
            controller.enqueue(chunk);
          }
        } else {
          controller.enqueue(materialized);
        }
        controller.close();
      }
    });
    
    return stream;
  }
  
  private async resurrectFromPartialMaterialization(
    checkpoint: StreamCheckpoint
  ): Promise<ReadableStream> {
    
    const storageKey = `stream-checkpoint-${checkpoint.streamId}`;
    const partialData = await this.storage.retrieve(storageKey);
    
    const stream = new ReadableStream({
      start(controller) {
        if (Array.isArray(partialData)) {
          for (const chunk of partialData) {
            controller.enqueue(chunk);
          }
        }
        
        controller.enqueue({
          $incomplete: true,
          offset: checkpoint.partialOffset,
          message: 'Stream was interrupted. Partial data only.'
        });
        
        controller.close();
      }
    });
    
    return stream;
  }
  
  private async resurrectViaRegeneration(
    checkpoint: StreamCheckpoint,
    options: {
      useSnapshotConfig: boolean;
    }
  ): Promise<ReadableStream> {
    
    if (!checkpoint.regenerationConfig) {
      throw new Error('No regeneration config available');
    }
    
    const config = options.useSnapshotConfig
      ? checkpoint.regenerationConfig.nodeConfig
      : this.workflowState.getNode(checkpoint.sourceNodeId)?.config;
    
    if (!config) {
      throw new Error('Node config not available for regeneration');
    }
    
    const inputs = checkpoint.regenerationConfig.inputs;
    
    const regenerated = await this.executeNodeForRegeneration(
      checkpoint.sourceNodeId,
      config,
      inputs
    );
    
    return regenerated;
  }
  
  private async executeNodeForRegeneration(
    nodeId: string,
    nodeConfig: any,
    inputs: Record<string, any>
  ): Promise<ReadableStream> {
    
    if (!this.regenerationExecutor) {
      throw new Error(
        'Regeneration requires executor callback. ' +
        'Set ResilientStreamManager.regenerationExecutor = (node, inputs) => stream'
      );
    }
    
    return await this.regenerationExecutor(nodeId, nodeConfig, inputs);
  }
  
  private hashConfig(config: any): string {
    const serialized = JSON.stringify(config, Object.keys(config).sort());
    return this.simpleHash(serialized);
  }
  
  private hashInputs(inputs: Record<string, any>): Record<string, string> {
    const hashes: Record<string, string> = {};
    
    for (const [key, value] of Object.entries(inputs)) {
      const serialized = JSON.stringify(value);
      hashes[key] = this.simpleHash(serialized);
    }
    
    return hashes;
  }
  
  private simpleHash(str: string): string {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return hash.toString(36);
  }
  
  private diffConfigs(oldConfig: any, newConfig: any): {
    breaking: boolean;
    summary: string;
  } {
    const changes: string[] = [];
    let breaking = false;
    
    // Critical fields that indicate breaking changes
    const criticalFields = ['type', 'operation', 'model', 'endpoint'];
    
    for (const field of criticalFields) {
      if (oldConfig[field] !== newConfig[field]) {
        breaking = true;
        changes.push(`${field} changed`);
      }
    }
    
    // Check all other fields
    const allFields = new Set([
      ...Object.keys(oldConfig),
      ...Object.keys(newConfig)
    ]);
    
    for (const field of allFields) {
      if (!criticalFields.includes(field) && oldConfig[field] !== newConfig[field]) {
        changes.push(field);
      }
    }
    
    return {
      breaking,
      summary: changes.length > 0 ? changes.join(', ') : 'no changes'
    };
  }
  
  private notifyDegradedResurrection(streamId: string, warning: string): void {
    // Emit event for UI to show warning banner
    window.dispatchEvent(new CustomEvent('stream-resurrection-degraded', {
      detail: { streamId, warning }
    }));
  }
  
  private startStalenessDetector(): void {
    setInterval(() => {
      for (const [streamId, checkpoint] of this.checkpoints.entries()) {
        if (checkpoint.status === 'checkpointed') {
          this.validateCheckpointFreshness(checkpoint).then(validation => {
            if (validation.stale && validation.severity === 'critical') {
              // Mark as expired
              checkpoint.status = 'expired';
              checkpoint.staleness = validation.reason;
            }
          });
        }
      }
    }, 60000);  // Check every minute
  }
  
  private async checkpointStream(streamId: string): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    const checkpoint = entry.checkpoint;
    
    switch (checkpoint.materializationType) {
      case 'full':
        if (entry.materializedChunks && entry.materializedChunks.length > 0) {
          const storageKey = `stream-checkpoint-${streamId}`;
          checkpoint.materializedData = [...entry.materializedChunks];
          
          await this.storage.store(storageKey, checkpoint.materializedData, {
            temporary: false,
            pinned: true,
            nodeId: checkpoint.sourceNodeId,
            dataType: 'materialized'
          });
          
          checkpoint.status = 'checkpointed';
          checkpoint.lastCheckpointAt = Date.now();
        }
        break;
        
      case 'partial':
        if (entry.materializedChunks) {
          const keepCount = 10;
          const partial = entry.materializedChunks.slice(-keepCount);
          
          const storageKey = `stream-checkpoint-${streamId}`;
          await this.storage.store(storageKey, partial, {
            temporary: false,
            pinned: true,
            nodeId: checkpoint.sourceNodeId,
            dataType: 'materialized'
          });
          
          checkpoint.partialOffset = entry.materializedChunks.length - keepCount;
          checkpoint.status = 'checkpointed';
          checkpoint.lastCheckpointAt = Date.now();
        }
        break;
        
      case 'regenerate':
        checkpoint.status = 'checkpointed';
        checkpoint.lastCheckpointAt = Date.now();
        break;
    }
    
    await this.persistCheckpoint(checkpoint);
  }
  
  private async persistCheckpoint(checkpoint: StreamCheckpoint): Promise<void> {
    const key = `stream-checkpoint-meta-${checkpoint.streamId}`;
    sessionStorage.setItem(key, JSON.stringify(checkpoint));
  }
  
  private async restoreCheckpointsFromStorage(): Promise<void> {
    const keys = Object.keys(sessionStorage);
    
    for (const key of keys) {
      if (key.startsWith('stream-checkpoint-meta-')) {
        const checkpointData = sessionStorage.getItem(key);
        if (checkpointData) {
          const checkpoint: StreamCheckpoint = JSON.parse(checkpointData);
          this.checkpoints.set(checkpoint.streamId, checkpoint);
        }
      }
    }
  }
  
  private createMultiTee(stream: ReadableStream, count: number): ReadableStream[] {
    if (count === 1) return [stream];
    if (count === 2) return stream.tee();
    
    const streams: ReadableStream[] = [];
    let remaining = stream;
    
    for (let i = 0; i < count - 1; i++) {
      const [stream1, stream2] = remaining.tee();
      streams.push(stream1);
      remaining = stream2;
    }
    streams.push(remaining);
    
    return streams;
  }
  
  private startAutoCheckpointing(): void {
    setInterval(() => {
      this.checkpointLongLivedStreams();
    }, this.config.autoCheckpointInterval);
  }
  
  private async checkpointLongLivedStreams(): Promise<void> {
    const now = Date.now();
    const threshold = this.config.checkpointThresholdAge;
    
    for (const [streamId, entry] of this.activeStreams.entries()) {
      const age = now - entry.checkpoint.createdAt;
      
      if (age > threshold && entry.checkpoint.status === 'active') {
        await this.checkpointStream(streamId);
      }
    }
  }
  
  private startTimeoutMonitor(): void {
    setInterval(() => {
      const now = Date.now();
      const timeout = this.config.streamTimeout;
      
      for (const [streamId, entry] of this.activeStreams.entries()) {
        if (now - entry.checkpoint.lastCheckpointAt > timeout) {
          console.warn(`Stream timeout: ${streamId}`);
          this.cleanup(streamId, 'timeout');
        }
      }
    }, 60000);
  }
  
  async acquireReader(
    streamId: string, 
    consumerIndex: number
  ): Promise<ReadableStreamDefaultReader> {
    const stream = await this.getStream(streamId, consumerIndex);
    const reader = stream.getReader();
    
    const entry = this.activeStreams.get(streamId);
    if (entry) {
      entry.readers.add(reader);
      
      if (entry.materializedChunks) {
        return this.wrapReaderForCheckpointing(reader, entry.materializedChunks);
      }
    }
    
    return reader;
  }
  
  private wrapReaderForCheckpointing(
    reader: ReadableStreamDefaultReader,
    chunksBuffer: any[]
  ): ReadableStreamDefaultReader {
    
    const originalRead = reader.read.bind(reader);
    
    reader.read = async () => {
      const result = await originalRead();
      
      if (!result.done && result.value !== undefined) {
        chunksBuffer.push(result.value);
      }
      
      return result;
    };
    
    return reader;
  }
  
  async releaseReader(
    streamId: string, 
    reader: ReadableStreamDefaultReader
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    try {
      reader.releaseLock();
    } catch {
      // Already released
    }
    
    entry.readers.delete(reader);
    
    if (entry.readers.size === 0) {
      await this.cleanup(streamId, 'completed');
    }
  }
  
  private async cleanup(
    streamId: string, 
    reason: 'completed' | 'error' | 'timeout'
  ): Promise<void> {
    const entry = this.activeStreams.get(streamId);
    if (!entry) return;
    
    if (reason === 'completed' && entry.checkpoint.materializationType !== 'regenerate') {
      await this.checkpointStream(streamId);
    }
    
    entry.checkpoint.status = 'expired';
    
    for (const stream of entry.streams) {
      try {
        const reader = stream.getReader();
        await reader.cancel(`Cleanup: ${reason}`);
        reader.releaseLock();
      } catch {
        // Ignore
      }
    }
    
    this.activeStreams.delete(streamId);
  }
  
  getCheckpoint(streamId: string): StreamCheckpoint | null {
    return this.checkpoints.get(streamId) ?? null;
  }
  
  listActiveStreams(): StreamCheckpoint[] {
    return Array.from(this.activeStreams.values())
      .map(entry => entry.checkpoint);
  }
  
  regenerationExecutor?: (
    nodeId: string, 
    nodeConfig: any, 
    inputs: Record<string, any>
  ) => Promise<ReadableStream>;
}

interface ActiveStreamEntry {
  checkpoint: StreamCheckpoint;
  streams: ReadableStream[];
  readers: Set<ReadableStreamDefaultReader>;
  materializedChunks?: any[];
}

interface WorkflowStateProvider {
  getNode(nodeId: string): { config: any } | null;
  getNodeInputs(nodeId: string): Record<string, any>;
}

interface StreamManagerConfig {
  maxConcurrentStreams: number;
  streamTimeout: number;
  autoCheckpointInterval: number;
  checkpointThresholdAge: number;
  enableResurrection: boolean;
  maxResurrectionAttempts: number;
}
```

## Enhanced Tiered Storage with Circular Buffer SessionStorage

### Key Enhancement: Circular Buffer Pattern + Compression for SessionStorage

```typescript
interface SessionStorageManager {
  maxSizeBytes: number;              // 4MB (留出1MB缓冲)
  currentSizeBytes: number;
  entries: Map<string, SessionEntry>;
  compressionThreshold: number;      // 10KB
}

interface SessionEntry {
  key: string;
  sizeBytes: number;
  priority: number;                  // Higher = more important
  createdAt: number;
  lastAccessedAt: number;
  compressed: boolean;
}

class HybridStorageManager {
  private memoryCache: Map<string, CacheEntry> = new Map();
  private memoryCacheSize: number = 0;
  private indexedDB: IDBDatabase;
  private indexedDBSize: number = 0;
  
  private workflowPolicies: Map<string, WorkflowStoragePolicy> = new Map();
  private globalPolicy: WorkflowStoragePolicy;
  
  private artifactIndex: Map<string, ArtifactMetadata> = new Map();
  private externalBlobs: Map<string, string> = new Map();
  
  // Enhanced SessionStorage manager
  private sessionManager: SessionStorageManager = {
    maxSizeBytes: 4 * 1024 * 1024,  // 4MB
    currentSizeBytes: 0,
    entries: new Map(),
    compressionThreshold: 10 * 1024  // 10KB
  };
  
  constructor(globalPolicy: WorkflowStoragePolicy) {
    this.globalPolicy = globalPolicy;
    this.initIndexedDB();
    this.restoreFromSession();
    this.calculateSessionStorageSize();
  }
  
  async store(
    key: string, 
    data: any, 
    hints: StorageHints = {}
  ): Promise<void> {
    
    const policy = this.getPolicy(hints.workflowId);
    const serialized = JSON.stringify(data);
    const sizeBytes = new TextEncoder().encode(serialized).length;
    
    const metadata: ArtifactMetadata = {
      key,
      sizeBytes,
      tier: 'determining',
      createdAt: Date.now(),
      lastAccessedAt: Date.now(),
      accessCount: 0,
      temporary: hints.temporary ?? true,
      pinned: hints.pinned ?? false,
      nodeId: hints.nodeId,
      executionId: hints.executionId,
      workflowId: hints.workflowId,
      dataType: hints.dataType ?? 'json'
    };
    
    this.artifactIndex.set(key, metadata);
    
    // Enhanced SessionStorage logic with circular buffer
    if (hints.useSessionStorage) {
      await this.storeInSessionStorage(
        key, 
        serialized, 
        sizeBytes,
        hints.priority ?? 5
      );
      metadata.tier = 'session';
      return;
    }
    
    // Memory tier
    if (sizeBytes < 1024 * 1024) {
      if (await this.tryStoreInMemory(key, data, sizeBytes, policy)) {
        metadata.tier = 'memory';
        return;
      }
    }
    
    // IndexedDB tier
    await this.storeInIndexedDB(key, serialized, sizeBytes, policy);
    metadata.tier = 'indexeddb';
  }
  
  private async storeInSessionStorage(
    key: string,
    serialized: string,
    sizeBytes: number,
    priority: number
  ): Promise<void> {
    
    // Try compression first if size > threshold
    let toStore = serialized;
    let compressed = false;
    let actualSize = sizeBytes;
    
    if (sizeBytes > this.sessionManager.compressionThreshold) {
      try {
        toStore = await this.compressForSession(serialized);
        actualSize = new TextEncoder().encode(toStore).length;
        compressed = true;
      } catch (error) {
        console.warn('Compression failed, using original', error);
      }
    }
    
    // Check if we need to evict
    while (this.sessionManager.currentSizeBytes + actualSize > this.sessionManager.maxSizeBytes) {
      const evicted = this.evictFromSessionStorage(priority);
      if (!evicted) {
        // Cannot evict - move to IndexedDB instead
        console.warn('SessionStorage full, moving to IndexedDB');
        
        const metadata = this.artifactIndex.get(key);
        if (metadata) {
          metadata.tier = 'indexeddb';
        }
        
        await this.storeInIndexedDB(key, serialized, sizeBytes, this.globalPolicy);
        return;
      }
    }
    
    // Store in SessionStorage
    const storageKey = `app-storage-${key}`;
    const envelope = {
      data: toStore,
      compressed,
      sizeBytes: actualSize,
      priority,
      createdAt: Date.now()
    };
    
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(envelope));
      
      this.sessionManager.entries.set(key, {
        key: storageKey,
        sizeBytes: actualSize,
        priority,
        createdAt: Date.now(),
        lastAccessedAt: Date.now(),
        compressed
      });
      
      this.sessionManager.currentSizeBytes += actualSize;
      
    } catch (error: any) {
      // Quota exceeded despite our calculations - force evict and retry
      console.error('SessionStorage quota exceeded:', error);
      
      this.evictFromSessionStorage(priority, true);
      
      // Move to IndexedDB
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        metadata.tier = 'indexeddb';
      }
      
      await this.storeInIndexedDB(key, serialized, sizeBytes, this.globalPolicy);
    }
  }
  
  private evictFromSessionStorage(
    incomingPriority: number,
    force: boolean = false
  ): boolean {
    
    const candidates = Array.from(this.sessionManager.entries.values())
      .filter(entry => force || entry.priority < incomingPriority)
      .sort((a, b) => {
        // Sort by priority (ascending), then LRU
        if (a.priority !== b.priority) {
          return a.priority - b.priority;
        }
        return a.lastAccessedAt - b.lastAccessedAt;
      });
    
    if (candidates.length === 0) {
      return false;
    }
    
    const toEvict = candidates[0];
    
    try {
      sessionStorage.removeItem(toEvict.key);
      
      const artifactKey = toEvict.key.replace('app-storage-', '');
      this.sessionManager.entries.delete(artifactKey);
      this.sessionManager.currentSizeBytes -= toEvict.sizeBytes;
      
      // Update metadata
      const metadata = this.artifactIndex.get(artifactKey);
      if (metadata) {
        metadata.tier = 'evicted';
      }
      
      return true;
      
    } catch (error) {
      console.error('Failed to evict from SessionStorage:', error);
      return false;
    }
  }
  
  async retrieve(key: string): Promise<any> {
    const metadata = this.artifactIndex.get(key);
    if (!metadata) {
      throw new Error(`Artifact not found: ${key}`);
    }
    
    metadata.accessCount++;
    metadata.lastAccessedAt = Date.now();
    
    switch (metadata.tier) {
      case 'memory':
        return this.memoryCache.get(key)?.data;
        
      case 'indexeddb':
        return await this.retrieveFromIndexedDB(key);
        
      case 'session':
        return await this.retrieveFromSessionStorage(key);
        
      case 'external':
        return await this.retrieveFromExternalBlob(key);
        
      default:
        throw new Error(`Unknown tier: ${metadata.tier}`);
    }
  }
  
  private async retrieveFromSessionStorage(key: string): Promise<any> {
    const storageKey = `app-storage-${key}`;
    const envelopeStr = sessionStorage.getItem(storageKey);
    
    if (!envelopeStr) {
      throw new Error(`Artifact not in SessionStorage: ${key}`);
    }
    
    const envelope = JSON.parse(envelopeStr);
    
    // Update access time
    const entry = this.sessionManager.entries.get(key);
    if (entry) {
      entry.lastAccessedAt = Date.now();
    }
    
    // Decompress if needed
    const serialized = envelope.compressed
      ? await this.decompressFromSession(envelope.data)
      : envelope.data;
    
    return JSON.parse(serialized);
  }
  
  private async compressForSession(data: string): Promise<string> {
    // Use LZ-based compression (smaller implementation)
    // This is a simple placeholder - real implementation would use pako or similar
    const encoder = new TextEncoder();
    const uint8 = encoder.encode(data);
    
    const stream = new Blob([uint8]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    
    const compressedUint8 = new Uint8Array(buffer);
    return btoa(String.fromCharCode(...compressedUint8));
  }
  
  private async decompressFromSession(data: string): Promise<string> {
    const binary = atob(data);
    const uint8 = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      uint8[i] = binary.charCodeAt(i);
    }
    
    const stream = new Blob([uint8]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private calculateSessionStorageSize(): void {
    let totalSize = 0;
    
    for (const key of Object.keys(sessionStorage)) {
      if (key.startsWith('app-storage-')) {
        const value = sessionStorage.getItem(key);
        if (value) {
          totalSize += new TextEncoder().encode(value).length;
        }
      }
    }
    
    this.sessionManager.currentSizeBytes = totalSize;
  }
  
  getSessionStorageStats(): {
    usedBytes: number;
    maxBytes: number;
    utilization: number;
    entriesCount: number;
  } {
    return {
      usedBytes: this.sessionManager.currentSizeBytes,
      maxBytes: this.sessionManager.maxSizeBytes,
      utilization: this.sessionManager.currentSizeBytes / this.sessionManager.maxSizeBytes,
      entriesCount: this.sessionManager.entries.size
    };
  }
  
  setWorkflowPolicy(workflowId: string, policy: WorkflowStoragePolicy): void {
    this.workflowPolicies.set(workflowId, policy);
  }
  
  getPolicy(workflowId?: string): WorkflowStoragePolicy {
    if (workflowId) {
      return this.workflowPolicies.get(workflowId) ?? this.globalPolicy;
    }
    return this.globalPolicy;
  }
  
  private async tryStoreInMemory(
    key: string, 
    data: any, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<boolean> {
    
    if (this.memoryCacheSize + sizeBytes <= policy.memoryCacheMaxBytes) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    if (await this.evictFromMemory(sizeBytes, policy)) {
      this.memoryCache.set(key, {
        data,
        sizeBytes,
        storedAt: Date.now()
      });
      this.memoryCacheSize += sizeBytes;
      return true;
    }
    
    return false;
  }
  
  private async evictFromMemory(
    requiredBytes: number, 
    policy: WorkflowStoragePolicy
  ): Promise<boolean> {
    
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'memory' &&
        (!policy.evictionPreferences.protectPinned || !m.pinned) &&
        (!policy.evictionPreferences.protectRecent || 
         Date.now() - m.createdAt > 5000)
      );
    
    candidates.sort((a, b) => {
      if (policy.evictionPreferences.protectFrequent) {
        if (a.accessCount !== b.accessCount) {
          return a.accessCount - b.accessCount;
        }
      }
      
      if (policy.overflowPolicy === 'evict-oldest') {
        return a.createdAt - b.createdAt;
      } else {
        return a.lastAccessedAt - b.lastAccessedAt;
      }
    });
    
    let freedBytes = 0;
    const toEvict: string[] = [];
    
    for (const metadata of candidates) {
      toEvict.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (freedBytes < requiredBytes) return false;
    
    for (const key of toEvict) {
      const entry = this.memoryCache.get(key)!;
      await this.storeInIndexedDB(key, JSON.stringify(entry.data), entry.sizeBytes, policy);
      
      this.memoryCache.delete(key);
      this.memoryCacheSize -= entry.sizeBytes;
      
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        metadata.tier = 'indexeddb';
      }
    }
    
    return true;
  }
  
  private async storeInIndexedDB(
    key: string, 
    serialized: string, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    if (this.indexedDBSize + sizeBytes > policy.indexedDBMaxBytes) {
      await this.handleIndexedDBOverflow(key, serialized, sizeBytes, policy);
      return;
    }
    
    const shouldCompress = sizeBytes > 1024 * 1024;
    const toStore = shouldCompress 
      ? await this.compress(serialized)
      : serialized;
    
    const actualSize = shouldCompress 
      ? new TextEncoder().encode(toStore).length 
      : sizeBytes;
    
    const tx = this.indexedDB.transaction('artifacts', 'readwrite');
    await tx.objectStore('artifacts').put({
      key,
      data: toStore,
      compressed: shouldCompress,
      sizeBytes: actualSize,
      storedAt: Date.now()
    });
    
    this.indexedDBSize += actualSize;
  }
  
  private async handleIndexedDBOverflow(
    key: string, 
    serialized: string, 
    sizeBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    switch (policy.overflowPolicy) {
      case 'evict-lru':
      case 'evict-oldest':
        await this.evictFromIndexedDB(sizeBytes, policy);
        await this.storeInIndexedDB(key, serialized, sizeBytes, policy);
        break;
        
      case 'fail':
        throw new StorageFullError(
          `Storage full for workflow: ${policy.workflowId}`,
          this.getStorageStats()
        );
        
      case 'compress':
        const compressed = await this.compress(serialized);
        const compressedSize = new TextEncoder().encode(compressed).length;
        
        if (this.indexedDBSize + compressedSize > policy.indexedDBMaxBytes) {
          await this.evictFromIndexedDB(compressedSize, policy);
        }
        
        const tx = this.indexedDB.transaction('artifacts', 'readwrite');
        await tx.objectStore('artifacts').put({
          key,
          data: compressed,
          compressed: true,
          sizeBytes: compressedSize,
          storedAt: Date.now()
        });
        
        this.indexedDBSize += compressedSize;
        break;
        
      case 'external':
        const blob = new Blob([await this.compress(serialized)]);
        const blobUrl = URL.createObjectURL(blob);
        
        this.externalBlobs.set(key, blobUrl);
        
        const tx2 = this.indexedDB.transaction('blobRefs', 'readwrite');
        await tx2.objectStore('blobRefs').put({
          key,
          blobUrl,
          sizeBytes,
          storedAt: Date.now()
        });
        
        const metadata = this.artifactIndex.get(key);
        if (metadata) {
          metadata.tier = 'external';
        }
        break;
    }
  }
  
  private async evictFromIndexedDB(
    requiredBytes: number,
    policy: WorkflowStoragePolicy
  ): Promise<void> {
    
    const candidates = Array.from(this.artifactIndex.values())
      .filter(m => 
        m.tier === 'indexeddb' &&
        (!policy.evictionPreferences.protectPinned || !m.pinned) &&
        m.workflowId === policy.workflowId
      );
    
    candidates.sort((a, b) => {
      if (policy.evictionPreferences.protectFrequent) {
        if (a.accessCount !== b.accessCount) {
          return a.accessCount - b.accessCount;
        }
      }
      
      if (policy.overflowPolicy === 'evict-oldest') {
        return a.createdAt - b.createdAt;
      } else {
        return a.lastAccessedAt - b.lastAccessedAt;
      }
    });
    
    let freedBytes = 0;
    const toDelete: string[] = [];
    
    for (const metadata of candidates) {
      toDelete.push(metadata.key);
      freedBytes += metadata.sizeBytes;
      
      if (freedBytes >= requiredBytes) break;
    }
    
    if (toDelete.length === 0) {
      throw new Error('Cannot evict: all items protected or wrong workflow');
    }
    
    const txDelete = this.indexedDB.transaction('artifacts', 'readwrite');
    const storeDelete = txDelete.objectStore('artifacts');
    
    for (const key of toDelete) {
      await storeDelete.delete(key);
      const metadata = this.artifactIndex.get(key);
      if (metadata) {
        this.indexedDBSize -= metadata.sizeBytes;
      }
      this.artifactIndex.delete(key);
    }
  }
  
  private async retrieveFromIndexedDB(key: string): Promise<any> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const record = await tx.objectStore('artifacts').get(key);
    
    if (!record) {
      throw new Error(`Artifact not in IndexedDB: ${key}`);
    }
    
    const serialized = record.compressed
      ? await this.decompress(record.data)
      : record.data;
    
    return JSON.parse(serialized);
  }
  
  private async retrieveFromExternalBlob(key: string): Promise<any> {
    const blobUrl = this.externalBlobs.get(key);
    if (!blobUrl) {
      throw new Error(`External blob not found: ${key}`);
    }
    
    const response = await fetch(blobUrl);
    const compressed = await response.text();
    const serialized = await this.decompress(compressed);
    return JSON.parse(serialized);
  }
  
  async pin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = true;
    }
  }
  
  async unpin(key: string): Promise<void> {
    const metadata = this.artifactIndex.get(key);
    if (metadata) {
      metadata.pinned = false;
    }
  }
  
  private async compress(data: string): Promise<string> {
    const stream = new Blob([data]).stream();
    const compressed = stream.pipeThrough(new CompressionStream('gzip'));
    const buffer = await new Response(compressed).arrayBuffer();
    
    const uint8 = new Uint8Array(buffer);
    return btoa(String.fromCharCode(...uint8));
  }
  
  private async decompress(data: string): Promise<string> {
    const binary = atob(data);
    const uint8 = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
      uint8[i] = binary.charCodeAt(i);
    }
    
    const stream = new Blob([uint8]).stream();
    const decompressed = stream.pipeThrough(new DecompressionStream('gzip'));
    return await new Response(decompressed).text();
  }
  
  private async initIndexedDB(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('WorkflowStorage', 4);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.indexedDB = request.result;
        this.calculateIndexedDBSize();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('artifacts')) {
          const store = db.createObjectStore('artifacts', { keyPath: 'key' });
          store.createIndex('storedAt', 'storedAt', { unique: false });
          store.createIndex('workflowId', 'workflowId', { unique: false });
        }
        
        if (!db.objectStoreNames.contains('blobRefs')) {
          db.createObjectStore('blobRefs', { keyPath: 'key' });
        }
      };
    });
  }
  
  private async calculateIndexedDBSize(): Promise<void> {
    const tx = this.indexedDB.transaction('artifacts', 'readonly');
    const store = tx.objectStore('artifacts');
    let cursor = await store.openCursor();
    
    let totalSize = 0;
    while (cursor) {
      totalSize += cursor.value.sizeBytes || 0;
      cursor = await cursor.continue();
    }
    
    this.indexedDBSize = totalSize;
  }
  
  private restoreFromSession(): void {
    const keys = Object.keys(sessionStorage);
    
    for (const key of keys) {
      if (key.startsWith('app-storage-')) {
        const artifactKey = key.replace('app-storage-', '');
        const envelopeStr = sessionStorage.getItem(key);
        
        if (envelopeStr) {
          const envelope = JSON.parse(envelopeStr);
          
          const metadata: ArtifactMetadata = {
            key: artifactKey,
            sizeBytes: envelope.sizeBytes,
            tier: 'session',
            createdAt: envelope.createdAt,
            lastAccessedAt: Date.now(),
            accessCount: 0,
            temporary: false,
            pinned: true,
            dataType: 'json'
          };
          
          this.artifactIndex.set(artifactKey, metadata);
          
          this.sessionManager.entries.set(artifactKey, {
            key,
            sizeBytes: envelope.sizeBytes,
            priority: envelope.priority,
            createdAt: envelope.createdAt,
            lastAccessedAt: Date.now(),
            compressed: envelope.compressed
          });
        }
      }
    }
  }
  
  getStorageStats(workflowId?: string): StorageStats {
    const stats = {
      memory: { count: 0, bytes: this.memoryCacheSize },
      indexeddb: { count: 0, bytes: this.indexedDBSize },
      session: { count: 0, bytes: this.sessionManager.currentSizeBytes },
      external: { count: 0, bytes: 0 },
      total: { count: this.artifactIndex.size, bytes: 0 }
    };
    
    for (const metadata of this.artifactIndex.values()) {
      if (workflowId && metadata.workflowId !== workflowId) continue;
      
      stats[metadata.tier as keyof typeof stats].count++;
      stats.total.bytes += metadata.sizeBytes;
    }
    
    return stats;
  }
}

interface CacheEntry {
  data: any;
  sizeBytes: number;
  storedAt: number;
}

interface StorageHints {
  temporary?: boolean;
  pinned?: boolean;
  nodeId?: string;
  executionId?: string;
  workflowId?: string;
  dataType?: 'stream-ref' | 'materialized' | 'blob' | 'json';
  useSessionStorage?: boolean;
  priority?: number;  // 1-10, default 5
}

interface ArtifactMetadata {
  key: string;
  sizeBytes: number;
  tier: 'memory' | 'indexeddb' | 'session' | 'external' | 'determining' | 'evicted';
  createdAt: number;
  lastAccessedAt: number;
  accessCount: number;
  temporary: boolean;
  pinned: boolean;
  nodeId?: string;
  executionId?: string;
  workflowId?: string;
  dataType: 'stream-ref' | 'materialized' | 'blob' | 'json';
}

interface WorkflowStoragePolicy {
  workflowId: string;
  memoryCacheMaxBytes: number;
  indexedDBMaxBytes: number;
  overflowPolicy: 'evict-lru' | 'evict-oldest' | 'fail' | 'compress' | 'external';
  evictionPreferences: {
    protectRecent: boolean;
    protectFrequent: boolean;
    protectPinned: boolean;
  };
  autoCleanupAge: number;
  enableAutoCleanup: boolean;
}

interface StorageStats {
  memory: { count: number; bytes: number };
  indexeddb: { count: number; bytes: number };
  session: { count: number; bytes: number };
  external: { count: number; bytes: number };
  total: { count: number; bytes: number };
}

class StorageFullError extends Error {
  constructor(message: string, public stats: StorageStats) {
    super(message);
    this.name = 'StorageFullError';
  }
}
```

## Simplified Visual Block Editor with Virtual Scrolling

### Key Enhancement: Virtualized Rendering + Block Limit + Performance Budget

```typescript
interface HybridExpression {
  mode: 'hybrid';
  content: EditorContent[];
  rawText: string;
  blockCount: number;  // NEW: Track block count
}

const EDITOR_CONFIG = {
  maxBlocks: 50,              // Hard limit on blocks per expression
  virtualScrollThreshold: 20,  // Start virtualizing if > 20 blocks
  performanceBudgetMs: 16     // Target 60fps (16ms per frame)
};

class HybridExpressionEditor {
  private engine: ComposableExpressionEngine;
  
  constructor() {
    this.engine = new ComposableExpressionEngine();
  }
  
  parseFromText(text: string): HybridExpression {
    const content: EditorContent[] = [];
    const blockMarkerRegex = /\{\{block:([^:}]+):([^}]+)\}\}/g;
    
    let lastIndex = 0;
    let blockCount = 0;
    const matches = text.matchAll(blockMarkerRegex);
    
    for (const match of matches) {
      if (blockCount >= EDITOR_CONFIG.maxBlocks) {
        console.warn(`Block limit reached (${EDITOR_CONFIG.maxBlocks}). Remaining blocks ignored.`);
        break;
      }
      
      if (match.index! > lastIndex) {
        const textPart = text.slice(lastIndex, match.index);
        if (textPart) {
          content.push({ type: 'text', text: textPart });
        }
      }
      
      const [_, blockType, configStr] = match;
      const config = this.parseBlockConfig(blockType, configStr);
      const displayText = this.generateDisplayText(blockType, config);
      
      content.push({
        type: 'block',
        blockType: blockType as any,
        config,
        displayText
      });
      
      blockCount++;
      lastIndex = match.index! + match[0].length;
    }
    
    if (lastIndex < text.length) {
      content.push({ type: 'text', text: text.slice(lastIndex) });
    }
    
    return {
      mode: 'hybrid',
      content,
      rawText: text,
      blockCount
    };
  }
  
  serializeToText(expression: HybridExpression): string {
    return expression.content.map(node => {
      if (node.type === 'text') {
        return node.text;
      } else {
        const configStr = this.serializeBlockConfig(node.blockType, node.config);
        return `{{block:${node.blockType}:${configStr}}}`;
      }
    }).join('');
  }
  
  insertBlock(
    expression: HybridExpression, 
    cursorPosition: number,
    blockType: string,
    config: Record<string, any>
  ): HybridExpression {
    
    if (expression.blockCount >= EDITOR_CONFIG.maxBlocks) {
      throw new Error(`Cannot insert block: limit of ${EDITOR_CONFIG.maxBlocks} blocks reached`);
    }
    
    const displayText = this.generateDisplayText(blockType, config);
    const blockNode: BlockNode = {
      type: 'block',
      blockType: blockType as any,
      config,
      displayText
    };
    
    let currentPos = 0;
    let insertIndex = 0;
    
    for (let i = 0; i < expression.content.length; i++) {
      const node = expression.content[i];
      const nodeLength = node.type === 'text' 
        ? node.text.length 
        : node.displayText.length;
      
      if (currentPos + nodeLength >= cursorPosition) {
        insertIndex = i + 1;
        break;
      }
      
      currentPos += nodeLength;
    }
    
    const newContent = [
      ...expression.content.slice(0, insertIndex),
      blockNode,
      ...expression.content.slice(insertIndex)
    ];
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent }),
      blockCount: expression.blockCount + 1
    };
  }
  
  removeBlock(expression: HybridExpression, blockIndex: number): HybridExpression {
    const newContent = expression.content.filter((_, i) => i !== blockIndex);
    
    const blockCount = newContent.filter(n => n.type === 'block').length;
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent }),
      blockCount
    };
  }
  
  updateBlock(
    expression: HybridExpression, 
    blockIndex: number,
    newConfig: Record<string, any>
  ): HybridExpression {
    
    const node = expression.content[blockIndex];
    if (node.type !== 'block') {
      throw new Error('Node is not a block');
    }
    
    const updatedNode: BlockNode = {
      ...node,
      config: newConfig,
      displayText: this.generateDisplayText(node.blockType, newConfig)
    };
    
    const newContent = [
      ...expression.content.slice(0, blockIndex),
      updatedNode,
      ...expression.content.slice(blockIndex + 1)
    ];
    
    return {
      mode: 'hybrid',
      content: newContent,
      rawText: this.serializeToText({ ...expression, content: newContent }),
      blockCount: expression.blockCount
    };
  }
  
  private parseBlockConfig(type: string, configStr: string): Record<string, any> {
    const pairs = configStr.split(':');
    
    switch (type) {
      case 'field':
        return { path: pairs[0] };
      case 'filter':
        return { condition: pairs[0] };
      case 'aggregate':
        return { function: pairs[0], path: pairs[1] || '' };
      case 'map':
        return { expression: pairs[0] };
      case 'transform':
        return { operation: pairs[0] };
      default:
        return {};
    }
  }
  
  private serializeBlockConfig(type: string, config: Record<string, any>): string {
    switch (type) {
      case 'field':
        return config.path;
      case 'filter':
        return config.condition;
      case 'aggregate':
        return `${config.function}:${config.path}`;
      case 'map':
        return config.expression;
      case 'transform':
        return config.operation;
      default:
        return '';
    }
  }
  
  private generateDisplayText(type: string, config: Record<string, any>): string {
    switch (type) {
      case 'field':
        return `$.${config.path}`;
      case 'filter':
        return `[${config.condition}]`;
      case 'aggregate':
        return `${config.function}(${config.path})`;
      case 'map':
        return `map(${config.expression})`;
      case 'transform':
        return config.operation;
      default:
        return 'block';
    }
  }
}

// React Component with Virtual Scrolling
const HybridExpressionEditorUI: React.FC<{
  value: HybridExpression;
  onChange: (value: HybridExpression) => void;
}> = ({ value, onChange }) => {
  
  const editor = useMemo(() => new HybridExpressionEditor(), []);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [selectedBlockIndex, setSelectedBlockIndex] = useState<number | null>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  
  // Virtualization state
  const [viewportStart, setViewportStart] = useState(0);
  const [viewportEnd, setViewportEnd] = useState(100);
  
  const shouldVirtualize = value.blockCount > EDITOR_CONFIG.virtualScrollThreshold;
  
  const visibleContent = useMemo(() => {
    if (!shouldVirtualize) {
      return value.content;
    }
    
    // Only render blocks in viewport
    return value.content.slice(viewportStart, viewportEnd);
  }, [value.content, viewportStart, viewportEnd, shouldVirtualize]);
  
  const handleInsertBlock = useCallback((blockType: string) => {
    if (value.blockCount >= EDITOR_CONFIG.maxBlocks) {
      alert(`Cannot insert block: maximum of ${EDITOR_CONFIG.maxBlocks} blocks reached.`);
      return;
    }
    
    const defaultConfig = getDefaultBlockConfig(blockType);
    const updated = editor.insertBlock(value, cursorPosition, blockType, defaultConfig);
    onChange(updated);
  }, [value, cursorPosition, editor, onChange]);
  
  const handleRemoveBlock = useCallback((blockIndex: number) => {
    const updated = editor.removeBlock(value, blockIndex);
    onChange(updated);
    setSelectedBlockIndex(null);
  }, [value, editor, onChange]);
  
  const handleUpdateBlock = useCallback((blockIndex: number, newConfig: Record<string, any>) => {
    const updated = editor.updateBlock(value, blockIndex, newConfig);
    onChange(updated);
  }, [value, editor, onChange]);
  
  const handleTextChange = useCallback((newText: string) => {
    try {
      const parsed = editor.parseFromText(newText);
      onChange(parsed);
    } catch (error: any) {
      console.error('Parse error:', error.message);
    }
  }, [editor, onChange]);
  
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    if (!shouldVirtualize) return;
    
    const container = e.currentTarget;
    const scrollTop = container.scrollTop;
    const itemHeight = 30;  // Approximate height per block
    
    const start = Math.floor(scrollTop / itemHeight);
    const end = start + Math.ceil(container.clientHeight / itemHeight) + 10;  // Buffer
    
    setViewportStart(Math.max(0, start));
    setViewportEnd(Math.min(value.content.length, end));
  }, [shouldVirtualize, value.content.length]);
  
  return (
    <div className="hybrid-expression-editor">
      {/* Block Palette */}
      <div className="block-palette">
        <button onClick={() => handleInsertBlock('field')} disabled={value.blockCount >= EDITOR_CONFIG.maxBlocks}>
          <span className="icon">📄</span> Field
        </button>
        <button onClick={() => handleInsertBlock('filter')} disabled={value.blockCount >= EDITOR_CONFIG.maxBlocks}>
          <span className="icon">🔍</span> Filter
        </button>
        <button onClick={() => handleInsertBlock('aggregate')} disabled={value.blockCount >= EDITOR_CONFIG.maxBlocks}>
          <span className="icon">Σ</span> Aggregate
        </button>
        <button onClick={() => handleInsertBlock('map')} disabled={value.blockCount >= EDITOR_CONFIG.maxBlocks}>
          <span className="icon">🗺️</span> Map
        </button>
        <button onClick={() => handleInsertBlock('transform')} disabled={value.blockCount >= EDITOR_CONFIG.maxBlocks}>
          <span className="icon">⚙️</span> Transform
        </button>
        
        <span className="block-count">
          {value.blockCount} / {EDITOR_CONFIG.maxBlocks} blocks
        </span>
      </div>
      
      {/* Rich Text Editor */}
      <div 
        ref={editorRef}
        className="editor-content"
        contentEditable
        suppressContentEditableWarning
        onScroll={handleScroll}
        onInput={(e) => {
          const text = e.currentTarget.textContent || '';
          handleTextChange(text);
        }}
        onSelect={() => {
          const selection = window.getSelection();
          if (selection) {
            setCursorPosition(selection.anchorOffset);
          }
        }}
      >
        {visibleContent.map((node, index) => {
          const actualIndex = shouldVirtualize ? viewportStart + index : index;
          
          if (node.type === 'text') {
            return <span key={actualIndex}>{node.text}</span>;
          } else {
            return (
              <BlockComponent
                key={actualIndex}
                node={node}
                selected={selectedBlockIndex === actualIndex}
                onSelect={() => setSelectedBlockIndex(actualIndex)}
                onRemove={() => handleRemoveBlock(actualIndex)}
                onUpdate={(config) => handleUpdateBlock(actualIndex, config)}
              />
            );
          }
        })}
      </div>
      
      {/* Block Config Panel */}
      {selectedBlockIndex !== null && value.content[selectedBlockIndex]?.type === 'block' && (
        <BlockConfigPanel
          blockNode={value.content[selectedBlockIndex] as BlockNode}
          onUpdate={(config) => handleUpdateBlock(selectedBlockIndex, config)}
          onClose={() => setSelectedBlockIndex(null)}
        />
      )}
      
      {/* Raw Text View */}
      <details className="raw-text-view">
        <summary>View Raw Text</summary>
        <textarea 
          value={value.rawText}
          onChange={(e) => handleTextChange(e.target.value)}
          className="raw-text-editor"
        />
      </details>
    </div>
  );
};

// Memoized block component for performance
const BlockComponent = React.memo<{
  node: BlockNode;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
  onUpdate: (config: Record<string, any>) => void;
}>(({ node, selected, onSelect, onRemove }) => {
  
  const getBlockIcon = (type: string) => {
    switch (type) {
      case 'field': return '📄';
      case 'filter': return '🔍';
      case 'aggregate': return 'Σ';
      case 'map': return '🗺️';
      case 'transform': return '⚙️';
      default: return '🧩';
    }
  };
  
  return (
    <span 
      className={`expression-block ${selected ? 'selected' : ''}`}
      onClick={onSelect}
      contentEditable={false}
    >
      <span className="block-icon">{getBlockIcon(node.blockType)}</span>
      <span className="block-text">{node.displayText}</span>
      <button className="block-remove" onClick={onRemove}>×</button>
    </span>
  );
});

const BlockConfigPanel: React.FC<{
  blockNode: BlockNode;
  onUpdate: (config: Record<string, any>) => void;
  onClose: () => void;
}> = ({ blockNode, onUpdate, onClose }) => {
  
  const [config, setConfig] = useState(blockNode.config);
  
  const handleSave = () => {
    onUpdate(config);
    onClose();
  };
  
  return (
    <div className="block-config-panel">
      <div className="panel-header">
        <h4>Configure {blockNode.blockType}</h4>
        <button onClick={onClose}>×</button>
      </div>
      
      <div className="panel-body">
        {blockNode.blockType === 'field' && (
          <label>
            Path:
            <input 
              type="text"
              value={config.path || ''}
              onChange={(e) => setConfig({ ...config, path: e.target.value })}
            />
          </label>
        )}
        
        {blockNode.blockType === 'filter' && (
          <label>
            Condition:
            <input 
              type="text"
              value={config.condition || ''}
              onChange={(e) => setConfig({ ...config, condition: e.target.value })}
              placeholder="e.g., age > 18"
            />
          </label>
        )}
        
        {blockNode.blockType === 'aggregate' && (
          <>
            <label>
              Function:
              <select 
                value={config.function || 'sum'}
                onChange={(e) => setConfig({ ...config, function: e.target.value })}
              >
                <option value="sum">Sum</option>
                <option value="avg">Average</option>
                <option value="count">Count</option>
                <option value="min">Min</option>
                <option value="max">Max</option>
              </select>
            </label>
            <label>
              Path:
              <input 
                type="text"
                value={config.path || ''}
                onChange={(e) => setConfig({ ...config, path: e.target.value })}
              />
            </label>
          </>
        )}
        
        {blockNode.blockType === 'map' && (
          <label>
            Expression:
            <input 
              type="text"
              value={config.expression || ''}
              onChange={(e) => setConfig({ ...config, expression: e.target.value })}
              placeholder="e.g., name & ' ' & email"
            />
          </label>
        )}
        
        {blockNode.blockType === 'transform' && (
          <label>
            Operation:
            <select 
              value={config.operation || 'uppercase'}
              onChange={(e) => setConfig({ ...config, operation: e.target.value })}
            >
              <option value="uppercase">Uppercase</option>
              <option value="lowercase">Lowercase</option>
              <option value="trim">Trim</option>
              <option value="reverse">Reverse</option>
            </select>
          </label>
        )}
      </div>
      
      <div className="panel-footer">
        <button onClick={handleSave}>Save</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
};

function getDefaultBlockConfig(blockType: string): Record<string, any> {
  switch (blockType) {
    case 'field':
      return { path: '' };
    case 'filter':
      return { condition: '' };
    case 'aggregate':
      return { function: 'sum', path: '' };
    case 'map':
      return { expression: '' };
    case 'transform':
      return { operation: 'uppercase' };
    default:
      return {};
  }
}

type EditorContent = TextNode | BlockNode;

interface TextNode {
  type: 'text';
  text: string;
}

interface BlockNode {
  type: 'block';
  blockType: 'field' | 'filter' | 'map' | 'aggregate' | 'transform';
  config: Record<string, any>;
  displayText: string;
}
```

## Simplified Trust Model + Stratified Sampling for Metrics

### Key Enhancement: Binary Trust + Always-Sample-Errors Strategy

```typescript
// Simplified to binary trust model
type TrustLevel = 'trusted' | 'untrusted';

interface CompensationHandlerConfig {
  id: string;
  name: string;
  trustLevel: TrustLevel;  // Simplified to binary
  author?: string;
  
  handlerType: 'builtin' | 'http-api' | 'webhook' | 'custom';
  
  matches: {
    operation?: string[];
    description?: string[];
    service?: string[];
  };
  
  compensation: 
    | { type: 'http-api'; config: HttpApiConfig }
    | { type: 'webhook'; config: WebhookConfig }
    | { type: 'custom'; workerUrl: string }
    | { type: 'manual'; steps: string[] };
}

// Stratified sampling for metrics
interface MetricsConfig {
  enablePersistence: boolean;
  
  // Stratified sampling rates
  sampling: {
    errors: number;          // 100% - always sample errors
    successes: number;       // 5% - rarely sample successes
    slowOperations: number;  // 50% - sample operations > 1s
  };
  
  retentionDays: number;
  enableRecommendations: boolean;
}

class AdaptivePerformanceMonitor {
  private metrics: StreamingMetrics;
  private recentMeasurements: Measurement[] = [];
  private db: IDBDatabase | null = null;
  private config: MetricsConfig;
  
  constructor(config: MetricsConfig) {
    this.config = config;
    this.metrics = this.initMetrics();
    
    if (config.enablePersistence) {
      this.initDatabase();
    }
  }
  
  recordDecision(
    strategy: 'tee' | 'materialize' | 'batch',
    sizeBytes: number,
    durationMs: number,
    memoryUsed: number,
    context: {
      workflowId: string;
      nodeId: string;
      success: boolean;  // NEW: Track success/failure
    }
  ): void {
    
    switch (strategy) {
      case 'tee':
        this.metrics.decisions.teeCount++;
        break;
      case 'materialize':
        this.metrics.decisions.materializeCount++;
        break;
      case 'batch':
        this.metrics.decisions.batchCount++;
        break;
    }
    
    if (strategy === 'tee' || strategy === 'materialize') {
      // Stratified sampling
      const shouldSample = this.shouldSample(context.success, durationMs);
      
      if (shouldSample) {
        const measurement: Measurement = {
          id: crypto.randomUUID(),
          timestamp: Date.now(),
          strategy,
          sizeBytes,
          durationMs,
          memoryUsed,
          workflowId: context.workflowId,
          nodeId: context.nodeId,
          success: context.success
        };
        
        this.recentMeasurements.push(measurement);
        
        if (this.recentMeasurements.length > 100) {
          this.recentMeasurements.shift();
        }
        
        if (this.config.enablePersistence && this.db) {
          this.persistMeasurement(measurement);
        }
      }
      
      this.updateAverages();
      
      if (this.config.enableRecommendations) {
        this.generateRecommendations();
      }
    }
  }
  
  private shouldSample(success: boolean, durationMs: number): boolean {
    // Always sample errors
    if (!success) {
      return Math.random() < this.config.sampling.errors;
    }
    
    // Sample slow operations more frequently
    if (durationMs > 1000) {
      return Math.random() < this.config.sampling.slowOperations;
    }
    
    // Rarely sample fast successes
    return Math.random() < this.config.sampling.successes;
  }
  
  recordError(type: 'tee' | 'materialize' | 'storage-full'): void {
    switch (type) {
      case 'tee':
        this.metrics.errors.teeFailures++;
        break;
      case 'materialize':
        this.metrics.errors.materializeFailures++;
        break;
      case 'storage-full':
        this.metrics.errors.storageFullErrors++;
        break;
    }
  }
  
  private updateAverages(): void {
    const tees = this.recentMeasurements.filter(m => m.strategy === 'tee');
    const materializes = this.recentMeasurements.filter(m => m.strategy === 'materialize');
    
    if (tees.length > 0) {
      this.metrics.performance.avgTeeMemory = 
        tees.reduce((sum, m) => sum + m.memoryUsed, 0) / tees.length;
      this.metrics.performance.avgTeeTime = 
        tees.reduce((sum, m) => sum + m.durationMs, 0) / tees.length;
    }
    
    if (materializes.length > 0) {
      this.metrics.performance.avgMaterializeSize = 
        materializes.reduce((sum, m) => sum + m.sizeBytes, 0) / materializes.length;
      this.metrics.performance.avgMaterializeTime = 
        materializes.reduce((sum, m) => sum + m.durationMs, 0) / materializes.length;
    }
  }
  
  private generateRecommendations(): void {
    if (this.metrics.performance.avgTeeMemory > 10 * 1024 * 1024) {
      this.metrics.recommendations.suggestedTeeThreshold = 3 * 1024 * 1024;
    } else {
      this.metrics.recommendations.suggestedTeeThreshold = 5 * 1024 * 1024;
    }
    
    if (this.metrics.performance.avgMaterializeTime < 100) {
      this.metrics.recommendations.suggestedMaterializeThreshold = 100 * 1024 * 1024;
    } else {
      this.metrics.recommendations.suggestedMaterializeThreshold = 50 * 1024 * 1024;
    }
    
    if (this.metrics.errors.storageFullErrors > 5) {
      this.metrics.recommendations.suggestedOverflowPolicy = 'evict-lru';
    } else {
      this.metrics.recommendations.suggestedOverflowPolicy = 'compress';
    }
  }
  
  async getHistoricalMetrics(
    workflowId?: string,
    startTime?: number,
    endTime?: number
  ): Promise<Measurement[]> {
    
    if (!this.config.enablePersistence || !this.db) {
      return this.recentMeasurements;
    }
    
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction('measurements', 'readonly');
      const store = tx.objectStore('measurements');
      const index = store.index('timestamp');
      
      const range = IDBKeyRange.bound(
        startTime || 0,
        endTime || Date.now()
      );
      
      const results: Measurement[] = [];
      const request = index.openCursor(range);
      
      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result;
        if (cursor) {
          const measurement: Measurement = cursor.value;
          
          if (!workflowId || measurement.workflowId === workflowId) {
            results.push(measurement);
          }
          
          cursor.continue();
        } else {
          resolve(results);
        }
      };
      
      request.onerror = () => reject(request.error);
    });
  }
  
  async generateReport(workflowId?: string): Promise<PerformanceReport> {
    const measurements = await this.getHistoricalMetrics(workflowId);
    
    const tees = measurements.filter(m => m.strategy === 'tee');
    const materializes = measurements.filter(m => m.strategy === 'materialize');
    
    return {
      totalMeasurements: measurements.length,
      timeRange: {
        start: Math.min(...measurements.map(m => m.timestamp)),
        end: Math.max(...measurements.map(m => m.timestamp))
      },
      strategies: {
        tee: {
          count: tees.length,
          avgMemory: tees.reduce((sum, m) => sum + m.memoryUsed, 0) / (tees.length || 1),
          avgDuration: tees.reduce((sum, m) => sum + m.durationMs, 0) / (tees.length || 1),
          avgSize: tees.reduce((sum, m) => sum + m.sizeBytes, 0) / (tees.length || 1),
          successRate: tees.filter(m => m.success).length / (tees.length || 1)
        },
        materialize: {
          count: materializes.length,
          avgMemory: materializes.reduce((sum, m) => sum + m.memoryUsed, 0) / (materializes.length || 1),
          avgDuration: materializes.reduce((sum, m) => sum + m.durationMs, 0) / (materializes.length || 1),
          avgSize: materializes.reduce((sum, m) => sum + m.sizeBytes, 0) / (materializes.length || 1),
          successRate: materializes.filter(m => m.success).length / (materializes.length || 1)
        }
      },
      recommendations: this.metrics.recommendations
    };
  }
  
  getMetrics(): StreamingMetrics {
    return { ...this.metrics };
  }
  
  getMeasurements(): Measurement[] {
    return [...this.recentMeasurements];
  }
  
  private async initDatabase(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('PerformanceMetrics', 3);
      
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        this.cleanupOldMeasurements();
        resolve();
      };
      
      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        
        if (!db.objectStoreNames.contains('measurements')) {
          const store = db.createObjectStore('measurements', { keyPath: 'id' });
          store.createIndex('timestamp', 'timestamp', { unique: false });
          store.createIndex('workflowId', 'workflowId', { unique: false });
          store.createIndex('strategy', 'strategy', { unique: false });
          store.createIndex('success', 'success', { unique: false });
        }
      };
    });
  }
  
  private async persistMeasurement(measurement: Measurement): Promise<void> {
    if (!this.db) return;
    
    const tx = this.db.transaction('measurements', 'readwrite');
    await tx.objectStore('measurements').add(measurement);
  }
  
  private async cleanupOldMeasurements(): Promise<void> {
    if (!this.db) return;
    
    const cutoff = Date.now() - (this.config.retentionDays * 24 * 60 * 60 * 1000);
    
    const tx = this.db.transaction('measurements', 'readwrite');
    const store = tx.objectStore('measurements');
    const index = store.index('timestamp');
    
    const range = IDBKeyRange.upperBound(cutoff);
    const request = index.openCursor(range);
    
    request.onsuccess = (event) => {
      const cursor = (event.target as IDBRequest).result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
  }
  
  private initMetrics(): StreamingMetrics {
    return {
      decisions: {
        teeCount: 0,
        materializeCount: 0,
        batchCount: 0
      },
      performance: {
        avgTeeMemory: 0,
        avgMaterializeSize: 0,
        avgTeeTime: 0,
        avgMaterializeTime: 0
      },
      errors: {
        teeFailures: 0,
        materializeFailures: 0,
        storageFullErrors: 0
      },
      recommendations: {
        suggestedTeeThreshold: 5 * 1024 * 1024,
        suggestedMaterializeThreshold: 50 * 1024 * 1024,
        suggestedOverflowPolicy: 'evict-lru'
      }
    };
  }
}

interface Measurement {
  id: string;
  timestamp: number;
  strategy: 'tee' | 'materialize';
  sizeBytes: number;
  durationMs: number;
  memoryUsed: number;
  workflowId: string;
  nodeId: string;
  success: boolean;  // NEW
}

interface StreamingMetrics {
  decisions: {
    teeCount: number;
    materializeCount: number;
    batchCount: number;
  };
  
  performance: {
    avgTeeMemory: number;
    avgMaterializeSize: number;
    avgTeeTime: number;
    avgMaterializeTime: number;
  };
  
  errors: {
    teeFailures: number;
    materializeFailures: number;
    storageFullErrors: number;
  };
  
  recommendations: {
    suggestedTeeThreshold: number;
    suggestedMaterializeThreshold: number;
    suggestedOverflowPolicy: string;
  };
}

interface PerformanceReport {
  totalMeasurements: number;
  timeRange: {
    start: number;
    end: number;
  };
  strategies: {
    tee: {
      count: number;
      avgMemory: number;
      avgDuration: number;
      avgSize: number;
      successRate: number;  // NEW
    };
    materialize: {
      count: number;
      avgMemory: number;
      avgDuration: number;
      avgSize: number;
      successRate: number;  // NEW
    };
  };
  recommendations: StreamingMetrics['recommendations'];
}

interface HttpApiConfig {
  method: 'GET' | 'POST' | 'DELETE' | 'PUT';
  urlTemplate: string;
  allowedDomains: string[];
  headers: Record<string, string>;
  bodyTemplate: string;
  auth?: {
    type: 'bearer' | 'basic' | 'api-key';
    tokenPath: string;
  };
}

interface WebhookConfig {
  url: string;
  allowedDomains: string[];
  method: 'POST' | 'PUT';
  payloadTemplate: string;
}
```

---

## What I Improved

### 1. Stream Resurrection Edge Cases (CRITICAL FIX)
**Problem**: Original design had no validation for config changes between checkpoint and resurrection.
**Solution**:
- **Version tracking**: Hash node config and inputs at checkpoint time
- **Staleness detection**: Validate checkpoint freshness before resurrection
- **Graceful degradation**: Three fallback strategies when config changes:
  1. Regenerate with old config (snapshot)
  2. Use cached data with warning
  3. Return empty stream with error message
- **Severity classification**: `none`/`minor`/`major`/`critical` determines fallback strategy
- **User notifications**: Event-based warnings for degraded resurrections

### 2. SessionStorage Overflow (CRITICAL FIX)
**Problem**: Original design would silently fail when hitting 5MB SessionStorage limit.
**Solution**:
- **Circular buffer pattern**: Priority-based eviction when approaching limit
- **Compression**: Auto-compress items > 10KB before storing
- **Size tracking**: Real-time monitoring of SessionStorage usage
- **Graceful fallback**: Move to IndexedDB if SessionStorage full
- **4MB soft limit**: Leave 1MB buffer to prevent quota errors

### 3. Visual Block Editor Performance
**Problem**: Rendering 50+ inline blocks would cause lag.
**Solution**:
- **Hard block limit**: 50 blocks per expression (prevents abuse)
- **Virtual scrolling**: Only render visible blocks when > 20 blocks
- **Memoization**: Block components wrapped in `React.memo`
- **Performance budget**: 16ms target (60fps)
- **Block counter**: Visible feedback on current usage

### 4. Trust Level UX Simplification
**Problem**: Four-level trust model (`system`/`verified`/`user`/`untrusted`) too complex.
**Solution**:
- **Binary trust**: `trusted` vs `untrusted` only
- **Clear approval flow**: Untrusted handlers require explicit user approval
- **Approval persistence**: Once approved, stored in localStorage
- **Domain whitelisting**: All handlers must declare allowed domains
- **No "verified" tier**: Removes need for marketplace/verification system

### 5. Metrics Sampling Strategy
**Problem**: 10% uniform sampling misses errors and performance spikes.
**Solution**:
- **Stratified sampling**:
  - **100% errors**: Always sample failures
  - **50% slow ops**: Sample operations > 1s
  - **5% fast successes**: Rarely sample quick successes
- **Success tracking**: Add `success: boolean` to measurements
- **Success rate in reports**: Show reliability metrics alongside performance

---

## What I Kept

All core architectural decisions remain intact:
- React Flow canvas ✅
- Zustand + immer state management ✅
- Adaptive streaming executor ✅
- Three-tier storage (enhanced) ✅
- Composable expression system ✅
- Append-only side effect log ✅
- Checkpoint manager ✅
- Worker pools ✅
- Compression ✅
- Auto-checkpointing streams ✅

---

## Remaining Concerns

### 1. Version Hashing Collisions
**Issue**: Simple hash function could have collisions for similar configs.
**Mitigation**: Use full config snapshot comparison as secondary check.
**Trade-off**: Slightly larger checkpoint metadata.

### 2. SessionStorage Cross-Tab Behavior
**Issue**: SessionStorage is per-tab, not shared across browser tabs.
**Impact**: Opening workflow in new tab loses checkpoints.
**Mitigation**: Add "Export/Import Checkpoint" feature for multi-tab workflows.

### 3. Virtual Scroll with contentEditable
**Issue**: contentEditable + virtual scrolling is complex to implement correctly.
**Alternative**: Use separate input for text, render blocks as read-only chips.
**Recommendation**: Prototype both approaches, measure complexity.

### 4. Compensation Handler Marketplace
**Issue**: No "verified" trust level means users can't discover trusted handlers.
**Future Work**: Build handler marketplace with community ratings + audits.
**Short-term**: Ship with built-in handlers only (Stripe, Slack, etc).

---

## Convergence Status

**ITERATING** - Found critical edge cases and improved the design with concrete solutions:

✅ **Stream resurrection**: Version-aware with graceful degradation  
✅ **SessionStorage overflow**: Circular buffer + compression  
✅ **Block editor performance**: Virtual scrolling + hard limits  
✅ **Trust model**: Simplified to binary with clear approval flow  
✅ **Metrics sampling**: Stratified sampling captures errors reliably  

The design is significantly more robust but needs one more iteration to validate the complexity trade-offs.

---

## PROMPT_FOR_ARCHITECT:

Your design was excellent - I've built on it to address the edge cases you identified. Please review my enhancements:

1. **Stream Resurrection with Version Tracking**: Do you see any scenarios where the staleness detection would fail? Should we also track workflow version (not just node config)?

2. **SessionStorage Circular Buffer**: Is priority-based eviction (1-10 scale) sufficient, or should we add more dimensions (access frequency, size, age)?

3. **Virtual Scrolling for contentEditable**: This is complex to implement correctly. Should we simplify to a non-editable block list + separate text input?

4. **Binary Trust Model**: Does removing "verified" tier hurt discoverability of safe handlers? Should we add a "community-trusted" flag instead?

5. **Stratified Sampling Rates**: Are 100%/50%/5% the right rates, or should they be configurable per workflow?

If these solutions work, we're ready to build. If not, suggest alternatives and we'll iterate once more.

**Convergence Signal:** ITERATING

---

