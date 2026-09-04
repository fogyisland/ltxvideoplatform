import type { Metadata } from "next";
import { Inter, Source_Serif_4, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { LanguageProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth-context";
import { ApiBaseProvider } from "@/lib/api-context";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});
const serif = Source_Serif_4({
  variable: "--font-serif-display",
  subsets: ["latin"],
  display: "swap",
});
const mono = JetBrains_Mono({
  variable: "--font-mono-display",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "LTX Studio",
  description: "Generate short videos from text prompts — running on your own GPU.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${serif.variable} ${mono.variable} antialiased`}
    >
      <body style={{ minHeight: "100vh" }}>
        <ApiBaseProvider>
          <LanguageProvider>
            <AuthProvider>{children}</AuthProvider>
          </LanguageProvider>
        </ApiBaseProvider>
      </body>
    </html>
  );
}