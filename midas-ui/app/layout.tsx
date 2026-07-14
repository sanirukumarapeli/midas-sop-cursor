import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// 1. Initialize the Inter font
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Midas S&OP AI Co-Pilot",
  description: "Strategic advisor for demand forecasting and supply risk analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} h-full antialiased`}
    >
      {/* 2. Inject inter.className to apply it globally */}
      <body className={`${inter.className} min-h-full flex flex-col`}>
        {children}
      </body>
    </html>
  );
}