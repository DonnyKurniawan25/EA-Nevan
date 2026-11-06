#ifndef GOLDSHIELD_METRICS_MQH
#define GOLDSHIELD_METRICS_MQH
#include <GoldShield/DomainTypes.mqh>

class GSMetrics
  {
private:
   int m_file;
   uint m_sequence;
   string m_session;
   bool m_failed;
public:
   GSMetrics(void) { m_file=INVALID_HANDLE; m_sequence=0; m_failed=false; }
   bool Healthy(void) { return m_file!=INVALID_HANDLE && !m_failed; }
   bool Init(const string key)
     {
      m_session=IntegerToString((long)GetMicrosecondCount());
      m_file=FileOpen("GoldShield\\"+key+".csv",FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_SHARE_READ,',');
      if(m_file==INVALID_HANDLE) return false;
      if(FileSize(m_file)==0)
         if(FileWrite(m_file,"event_id","server_time","utc_time","clock_source","event",
                      "symbol","candle_id_server","reason_code","details")==0) return false;
      FileSeek(m_file,0,SEEK_END);
      return true;
     }
   void Event(const string event,const string reason,const string details="",const datetime candle=0)
     {
      m_sequence++;
      string utc="";
      string source="BROKER_SERVER_AND_PC_UTC";
      if(MQLInfoInteger(MQL_TESTER)) source="TESTER_SERVER_ONLY";
      else utc=TimeToString(TimeGMT(),TIME_DATE|TIME_SECONDS);
      string id=m_session+"-"+IntegerToString(m_sequence);
      Print("GOLDSHIELD ",event," | ",reason," | ",details);
      if(m_file!=INVALID_HANDLE)
        {
         if(FileWrite(m_file,id,TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS),utc,source,
                      event,_Symbol,(long)candle,reason,details)==0) m_failed=true;
         ResetLastError();
         FileFlush(m_file);
         if(GetLastError()!=0) m_failed=true;
        }
     }
   void Release(void)
     {
      if(m_file!=INVALID_HANDLE) { FileFlush(m_file); FileClose(m_file); }
      m_file=INVALID_HANDLE;
     }
  };
class GSStateMachine
  {
private:
   GSState m_state;
   string m_reason;
public:
   GSStateMachine(void) { m_state=INIT; m_reason="STARTUP"; }
   GSState State(void) { return m_state; }
   string Reason(void) { return m_reason; }
   void Set(const GSState next,const string reason,GSMetrics &log)
     {
      if(next==m_state && reason==m_reason) return;
      log.Event("STATE",reason,EnumToString(m_state)+" -> "+EnumToString(next));
      m_state=next; m_reason=reason;
     }
  };
#endif
