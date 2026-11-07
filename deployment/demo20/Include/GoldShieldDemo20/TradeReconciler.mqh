#ifndef GOLDSHIELD_TRADE_RECONCILER_MQH
#define GOLDSHIELD_TRADE_RECONCILER_MQH
#include <GoldShieldDemo20/DomainTypes.mqh>

class GSTradeReconciler
  {
public:
   bool Read(const string symbol,const ulong magic,GSOwnedPosition &owned,string &reason)
     {
      ZeroMemory(owned);
      for(int i=PositionsTotal()-1;i>=0;i--)
        {
         ulong ticket=PositionGetTicket(i);
         if(ticket==0 || !PositionSelectByTicket(ticket))
            return GSReject(reason,"POSITION_SNAPSHOT_UNAVAILABLE");
         if(PositionGetString(POSITION_SYMBOL)!=symbol ||
            (ulong)PositionGetInteger(POSITION_MAGIC)!=magic) continue;
         string comment=PositionGetString(POSITION_COMMENT);
         if(StringFind(comment,"GS2|")!=0) { owned.collision=true; continue; }
         owned.count++;
         owned.ticket=ticket;
         owned.identifier=PositionGetInteger(POSITION_IDENTIFIER);
         owned.direction=PositionGetInteger(POSITION_TYPE);
         owned.volume=PositionGetDouble(POSITION_VOLUME);
         owned.sl=PositionGetDouble(POSITION_SL);
         owned.floating_pl+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
         owned.opened_at=(datetime)PositionGetInteger(POSITION_TIME);
         owned.comment=comment;
        }
      for(int i=OrdersTotal()-1;i>=0;i--)
        {
         ulong order=OrderGetTicket(i);
         if(order==0) return GSReject(reason,"ORDER_SNAPSHOT_UNAVAILABLE");
         if(OrderGetString(ORDER_SYMBOL)==symbol && (ulong)OrderGetInteger(ORDER_MAGIC)==magic)
            owned.pending_orders++;
        }
      if(owned.collision) return GSReject(reason,"MAGIC_OR_COMMENT_COLLISION");
      if(owned.count>MaxAccountPositions) return GSReject(reason,"MULTIPLE_POSITIONS_UNSUPPORTED_PHASE1");
      return true;
     }
  };
#endif
