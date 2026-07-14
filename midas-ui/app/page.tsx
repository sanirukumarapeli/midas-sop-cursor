import ChatDashboard from "@/components/ChatDashboard";
import Sidebar from "@/components/Sidebar";

export default function Home() {
  return (
    <div className="flex h-screen w-full bg-[#1a1a1a] overflow-hidden">
      <Sidebar />

      <main className="flex-1 h-full overflow-hidden relative">
        <ChatDashboard />
      </main>
    </div>
  );
}