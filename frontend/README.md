# 🚀🧠 Deepagents UI

[Deepagents](https://github.com/langchain-ai/deepagents) is a simple, open source agent harness that implements a few generally useful tools, including planning (prior to task execution), computer access (giving the able access to a shell and a filesystem), and sub-agent delegation (isolated task execution). This is a UI for interacting with deepagents.

This frontend is part of the [hostagent monorepo](../README.md). For backend setup, see [backend/README.md](../backend/README.md).

## 🚀 Quickstart

### Prerequisites

- Node.js 18+ (recommended: use the version specified in `.nvmrc`)
- Yarn package manager
- A running LangGraph deployment (see backend setup below)

### Install Dependencies

```bash
# From the frontend directory
cd frontend
yarn install
```

### Environment Variables (Optional)

You can optionally create a `.env.local` file to set the LangSmith API key:

```bash
# Copy the example file
cp .env.local.example .env.local

# Edit .env.local and add your LangSmith API key (optional)
NEXT_PUBLIC_LANGSMITH_API_KEY=lsv2_pt_...
```

**Note:** Settings configured in the UI take precedence over environment variables.

### Start the Development Server

```bash
yarn dev
```

The application will be available at [http://localhost:3000](http://localhost:3000).

## 🔧 Configuration

When you first open the application, you'll be prompted to configure:

### For Local Development with the Research Agent Example

1. **Start the LangGraph API** (see [Backend Setup](#backend-setup) below)
2. **Configure in the UI**:
   - **Deployment URL**: `http://127.0.0.1:2024`
   - **Assistant ID**: `researchAgent`
   - **LangSmith API Key**: (optional) Your LangSmith API key

### Backend Setup

To run the research agent locally:

```bash
# From the project root
cd examples/research

# Initialize the LangGraph environment (first time only)
./init_langgraph.sh

# Start the LangGraph server
source .venv/bin/activate
langgraph dev
```

You will see output like:

```
╦  ┌─┐┌┐┌┌─┐╔═╗┬─┐┌─┐┌─┐┬ ┬
║  ├─┤││││ ┬║ ╦├┬┘├─┤├─┘├─┤
╩═╝┴ ┴┘└┘└─┘╚═╝┴└─┴ ┴┴  ┴ ┴

- 🚀 API: http://127.0.0.1:2024
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- 📚 API Docs: http://127.0.0.1:2024/docs
```

The assistant ID is defined in `examples/research/langgraph.json`:

```json
{
  "graphs": {
    "researchAgent": "./research_agent.py:agent"
  }
}
```

**Open Deepagents UI** at [http://localhost:3000](http://localhost:3000) and configure it using the values above.

## 💡 Usage

You can interact with the deployment via the chat interface and can edit settings at any time by clicking on the Settings button in the header.

### Features

- **Chat Interface**: Interact with the deep agent through a conversational UI
- **Debug Mode**: Execute agents step-by-step for debugging and optimization
- **File Viewer**: View files in the agent's virtual filesystem
- **Thread Management**: Manage multiple conversation threads
- **Tool Approval**: Review and approve tool executions when required

### Debug Mode

You can run your Deep Agents in Debug Mode, which will execute the agent step by step. This allows you to re-run specific steps of the agent. This is intended to be used alongside the optimizer.

You can also turn off Debug Mode to run the full agent end-to-end.

## 🛠️ Development Commands

```bash
# Start development server
yarn dev

# Build for production
yarn build

# Start production server
yarn start

# Run linter
yarn lint

# Auto-fix linting issues
yarn lint:fix

# Format code
yarn format

# Check code formatting
yarn format:check
```

## 📦 Technology Stack

- **Framework**: Next.js 16 with App Router
- **Language**: TypeScript
- **UI Components**: Radix UI + Tailwind CSS
- **State Management**: React Context + SWR
- **LangGraph SDK**: @langchain/langgraph-sdk
- **Markdown**: react-markdown with syntax highlighting

## 🔗 Related Links

- [Main Project README](../README.md)
- [Backend Documentation](../backend/README.md)
- [Deepagents GitHub](https://github.com/langchain-ai/deepagents)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)

## 📚 Resources

If the term "Deep Agents" is new to you, check out these videos:

- [What are Deep Agents?](https://www.youtube.com/watch?v=433SmtTc0TA)
- [Implementing Deep Agents](https://www.youtube.com/watch?v=TTMYJAw5tiA&t=701s)
