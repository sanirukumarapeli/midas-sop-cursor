import ChatDashboard from "@/components/ChatDashboard";
import Sidebar from "@/components/Sidebar";

export default function Home() {
  return (
    <div className="flex h-screen w-full bg-slate-950 overflow-hidden">
      {/* Permanent Left Navigation Panel */}
      <Sidebar />
      
      {/* Main Application Chat Window */}
      <main className="flex-1 h-full overflow-hidden relative">
        <ChatDashboard />
      </main>
    </div>
  );
}