import { Inter } from "next/font/google";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Toaster } from "sonner";
import "./globals.css";
import Script from "next/script";

const inter = Inter({ subsets: ["latin"] });

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
    >
      <body
        className={inter.className}
        suppressHydrationWarning
      >
        <NuqsAdapter>{children}</NuqsAdapter>
        <Toaster />
      
      {/* WUUNU SNIPPET - DON'T CHANGE THIS (START) */}
      {process.env.NODE_ENV !== "production" && (
        <>
          <Script id="wuunu-ws" strategy="afterInteractive">
            { `window.__WUUNU_WS__ = "http://127.0.0.1:54586/";` }
          </Script>
          <Script
            id="wuunu-widget"
            src="https://cdn.jsdelivr.net/npm/@wuunu/widget@0.1?cacheParam=180"
            strategy="afterInteractive"
            crossOrigin="anonymous"
          />
        </>
      )}
      {/* WUUNU SNIPPET - DON'T CHANGE THIS (END) */}
</body>
    </html>
  );
}
