'use client';

import { useRef, useState, useCallback, useEffect } from 'react';
import { Room, RoomEvent, Track, LocalAudioTrack, Participant, ParticipantEvent } from 'livekit-client';

export interface LiveKitConfig {
  url: string;
  token: string;
}

export interface AgentState {
  isSpeaking: boolean;
  isListening: boolean;
}

export interface TranscriptionMessage {
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  isFinal: boolean;  // 標記是否為最終版本
}

export function useLiveKit() {
  const roomRef = useRef<Room | null>(null);
  const localAudioTrackRef = useRef<LocalAudioTrack | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [agentAudioElement, setAgentAudioElement] = useState<HTMLAudioElement | null>(null);
  const [agentState, setAgentState] = useState<AgentState>({
    isSpeaking: false,
    isListening: false,
  });
  const [error, setError] = useState<Error | null>(null);
  const [transcriptions, setTranscriptions] = useState<TranscriptionMessage[]>([]);

  // ✅ 新增：本地使用者是否正在說話
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  // 用於解除綁定事件的 handler ref
  const localSpeakingHandlerRef = useRef<((speaking: boolean) => void) | null>(null);

  // ✅ 簡化版：一對一場景下直接判斷（房間內只有 user 和 agent）
  const isAgentParticipant = useCallback((participant: Participant): boolean => {
    // 方法 1：使用 Metadata（推薦，更明確）
    try {
      const metadata = JSON.parse(participant.metadata || '{}');
      if (metadata.role === 'agent') return true;
    } catch {}

    // 方法 2：一對一場景簡化判斷
    // 房間內只有 2 個參與者，非本地參與者即為 Agent
    return participant.identity !== roomRef.current?.localParticipant.identity;
  }, []);

  // 連接到 LiveKit 房間
  const connect = useCallback(async (config: LiveKitConfig) => {
    try {
      const room = new Room({
        // 啟用自適應串流和降噪
        adaptiveStream: true,
        dynacast: true,
      });
      roomRef.current = room;

      // ✅ 監聽本地使用者說話狀態
      localSpeakingHandlerRef.current = (speaking: boolean) => {
        console.log('本地使用者是否正在說話:', speaking);
        setIsUserSpeaking(speaking);
      };
      room.localParticipant.on(
        ParticipantEvent.IsSpeakingChanged,
        localSpeakingHandlerRef.current
      );

      // 監聽連接事件
      room.on(RoomEvent.Connected, () => {
        console.log('✅ Connected to LiveKit room');
        console.log('   Room SID:', room.sid);
        console.log('   Local participant:', room.localParticipant.identity);
        console.log('   Remote participants count:', room.remoteParticipants.size);
        setIsConnected(true);
        setError(null);
      });

      room.on(RoomEvent.Disconnected, (reason) => {
        console.log('❌ Disconnected from LiveKit room:', reason);
        console.log('   Disconnect reason type:', typeof reason);
        console.log('   Was connected for:', Date.now() - (window as any).connectionStartTime, 'ms');
        setIsConnected(false);
        setAgentState({ isSpeaking: false, isListening: false });
        setIsUserSpeaking(false); // ✅ 重置使用者說話狀態
      });

      // 記錄連接狀態變化
      room.on(RoomEvent.ConnectionStateChanged, (state) => {
        console.log('📡 Connection state changed:', state);
        console.log('   Room state:', room.state);
        console.log('   Is connected:', room.isConnected);
      });

      // 記錄連接品質
      room.on(RoomEvent.ConnectionQualityChanged, (quality, participant) => {
        console.log('📶 Connection quality changed:', quality, 'for:', participant.identity);
      });

      // 記錄重新連接嘗試
      room.on(RoomEvent.Reconnecting, () => {
        console.log('🔄 Attempting to reconnect...');
      });

      room.on(RoomEvent.Reconnected, () => {
        console.log('✅ Successfully reconnected');
      });

      // 監聽參與者加入
      room.on(RoomEvent.ParticipantConnected, (participant) => {
        console.log('👤 Participant connected:', participant.identity);
        console.log('   Participant SID:', participant.sid);
        console.log('   Is local:', participant.isLocal);
        console.log('   Metadata:', participant.metadata);
        console.log('   Tracks:', participant.trackPublications.size);

        if (isAgentParticipant(participant)) {
          console.log('🤖 This is the Agent participant');
        }
      });

      // 監聽參與者離開
      room.on(RoomEvent.ParticipantDisconnected, (participant) => {
        console.log('👤 Participant disconnected:', participant.identity);
        console.log('   Was Agent:', isAgentParticipant(participant));
      });

      // ✅ 監聽 Metadata 變更（用於識別 Agent）
      room.on(RoomEvent.ParticipantMetadataChanged, (metadata, participant) => {
        console.log('📝 Participant metadata changed:', participant.identity, metadata);

        if (isAgentParticipant(participant)) {
          console.log('✅ Agent participant identified:', participant.identity);
        }
      });

      // ✅ 監聽遠端音訊軌道（Agent TTS） - 使用官方推薦方式
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        console.log('🎵 Track subscribed:', track.kind, participant.identity);

        if (track.kind === Track.Kind.Audio && isAgentParticipant(participant)) {
          console.log('🤖 Agent audio track detected, attaching...');

          // ✅ 官方建議：直接使用 track.attach() 返回的 HTMLAudioElement
          const audioElement = track.attach() as HTMLAudioElement;

          // 設置音量
          audioElement.volume = 1.0;
          audioElement.style.display = 'none';

          // 添加到 DOM
          document.body.appendChild(audioElement);

          console.log('✅ Agent TTS audio element attached');
          console.log('   Audio element volume:', audioElement.volume);
          console.log('   Audio element muted:', audioElement.muted);
          console.log('   Audio element autoplay:', audioElement.autoplay);
          console.log('   Has srcObject:', !!audioElement.srcObject);

          setAgentAudioElement(audioElement);

          // 監聽播放狀態
          audioElement.addEventListener('play', () => {
            console.log('▶️ Agent audio started playing');
            setAgentState(prev => ({ ...prev, isSpeaking: true }));
          });

          audioElement.addEventListener('pause', () => {
            console.log('⏸️ Agent audio paused');
            setAgentState(prev => ({ ...prev, isSpeaking: false }));
          });

          audioElement.addEventListener('ended', () => {
            console.log('⏹️ Agent audio ended');
            setAgentState(prev => ({ ...prev, isSpeaking: false }));
          });

          // 監聽錯誤（只記錄有意義的錯誤）
          audioElement.addEventListener('error', (event) => {
            const target = event.target as HTMLAudioElement;
            const error = target.error;

            // 只記錄真正有錯誤代碼和訊息的情況
            if (error && error.code && error.message) {
              console.error('❌ Audio playback error:', {
                code: error.code,
                message: error.message,
                type: error.code === 1 ? 'MEDIA_ERR_ABORTED' :
                      error.code === 2 ? 'MEDIA_ERR_NETWORK' :
                      error.code === 3 ? 'MEDIA_ERR_DECODE' :
                      error.code === 4 ? 'MEDIA_ERR_SRC_NOT_SUPPORTED' : 'UNKNOWN',
              });
            }
          });
        }
      });

      // ✅ 處理瀏覽器自動播放限制
      room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
        console.log('🔊 Audio playback status changed');
        console.log('   Can playback audio:', room.canPlaybackAudio);

        if (!room.canPlaybackAudio) {
          console.warn('⚠️ Audio playback blocked by browser, need user interaction');
          setError(new Error('請點擊任意處啟用音訊播放'));
        }
      });

      // 監聽錯誤
      room.on(RoomEvent.ConnectionQualityChanged, (quality, participant) => {
        if (quality === 'poor') {
          console.warn('⚠️ Connection quality is poor for:', participant.identity);
        }
      });

      // ✅ 監聽 LiveKit 原生 Transcription 事件（Agent TTS 即時字幕）
      room.on(RoomEvent.TranscriptionReceived, (segments, participant, publication) => {
        console.log('📝 Transcription received from:', participant?.identity);
        console.log('   Segments:', segments);

        segments.forEach(segment => {
          console.log(`   [${segment.final ? 'Final' : 'Interim'}] ${segment.text}`);

          // 判斷是 agent 還是 user（agent 通常有 metadata.role === "agent"）
          const isAgent = participant && isAgentParticipant(participant);
          const role = isAgent ? 'assistant' : 'user';

          if (segment.final) {
            // 最終版本：檢查是否需要取代最後一則 interim 訊息
            setTranscriptions(prev => {
              const lastMsg = prev[prev.length - 1];
              if (lastMsg && lastMsg.role === role && !lastMsg.isFinal) {
                // 取代最後一則 interim 訊息為 final 版本
                return [
                  ...prev.slice(0, -1),
                  { role: role, text: segment.text, timestamp: new Date(), isFinal: true }
                ];
              } else {
                // 新增 final 訊息
                return [...prev, {
                  role: role,
                  text: segment.text,
                  timestamp: new Date(),
                  isFinal: true
                }];
              }
            });
          } else {
            // Interim 串流：直接取代最後一則同角色訊息（segment.text 已經是完整文字）
            setTranscriptions(prev => {
              const lastMsg = prev[prev.length - 1];
              if (lastMsg && lastMsg.role === role && !lastMsg.isFinal) {
                // 直接取代為新的完整文字
                return [
                  ...prev.slice(0, -1),
                  { role: role, text: segment.text, timestamp: lastMsg.timestamp, isFinal: false }
                ];
              } else {
                // 建立第一個 interim 訊息
                return [...prev, {
                  role: role,
                  text: segment.text,
                  timestamp: new Date(),
                  isFinal: false
                }];
              }
            });
          }
        });
      });

      // ✅ 監聽 DataChannel 訊息（僅用於接收 User ASR）
      room.on(RoomEvent.DataReceived, (payload, participant, kind) => {
        try {
          const message = JSON.parse(new TextDecoder().decode(payload));
          console.log('📨 Received DataChannel message:', message);

          if (message.type === 'transcription' && message.role === 'user') {
            console.log(`[user]: ${message.text}`);

            if (message.is_final) {
              setTranscriptions(prev => [...prev, {
                role: 'user',
                text: message.text,
                timestamp: new Date()
              }]);
            }
          }
        } catch (error) {
          console.error('❌ Failed to parse DataChannel message:', error);
        }
      });

      // 記錄連接開始時間
      (window as any).connectionStartTime = Date.now();
      console.log('🔌 Attempting to connect to LiveKit...');
      console.log('   URL:', config.url);
      console.log('   Token (first 50 chars):', config.token.substring(0, 50) + '...');

      // 連接到房間
      await room.connect(config.url, config.token);

      console.log('📊 Initial room state after connect:');
      console.log('   Room name:', room.name);
      console.log('   Room SID:', room.sid);
      console.log('   Local participant:', room.localParticipant?.identity);
      console.log('   Remote participants:', Array.from(room.remoteParticipants.keys()));

      return room;
    } catch (error) {
      console.error('Failed to connect to LiveKit:', error);
      setError(error as Error);
      throw error;
    }
  }, [isAgentParticipant]);

  // 發布麥克風音訊
  const publishMicrophone = useCallback(async (stream: MediaStream) => {
    console.log('📢 publishMicrophone called, roomRef.current:', !!roomRef.current);

    if (!roomRef.current) {
      console.error('❌ Room not connected, cannot publish microphone');
      throw new Error('Room not connected');
    }

    try {
      const mediaStreamTrack = stream.getAudioTracks()[0];
      console.log('🎙️ MediaStreamTrack details:');
      console.log('   Track ID:', mediaStreamTrack.id);
      console.log('   Track label:', mediaStreamTrack.label);
      console.log('   Track enabled:', mediaStreamTrack.enabled);
      console.log('   Track muted:', mediaStreamTrack.muted);
      console.log('   Track readyState:', mediaStreamTrack.readyState);
      console.log('   Track settings:', mediaStreamTrack.getSettings());

      // ✅ 檢查音訊是否真的有數據
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      source.connect(analyser);

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      // 檢查音訊數據
      const checkAudio = () => {
        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
        console.log('🎵 Audio level:', average.toFixed(2), '(should be >0 when speaking)');
      };

      // 每秒檢查一次
      const intervalId = setInterval(checkAudio, 1000);
      setTimeout(() => clearInterval(intervalId), 10000); // 10秒後停止

      console.log('🎵 Creating LocalAudioTrack...');
      const audioTrack = new LocalAudioTrack(mediaStreamTrack, {
        name: 'microphone',
      });

      console.log('📤 Publishing track to LiveKit...');
      await roomRef.current.localParticipant.publishTrack(audioTrack, {
        name: 'microphone',
        source: Track.Source.Microphone,  // ✅ 明確指定音訊來源
        audioPriority: 'high',
      });

      localAudioTrackRef.current = audioTrack;
      setIsPublishing(true);
      setAgentState(prev => ({ ...prev, isListening: true }));

      console.log('✅ Microphone published to LiveKit successfully');

      // 監控音訊軌道狀態
      console.log('   Track enabled:', audioTrack.isEnabled);
      console.log('   Track muted:', audioTrack.isMuted);
      console.log('   Track SID:', audioTrack.sid);

      // ✅ 監聽 track 的統計資訊
      setInterval(() => {
        if (audioTrack && roomRef.current) {
          console.log('📊 LocalAudioTrack stats:');
          console.log('   Enabled:', audioTrack.isEnabled);
          console.log('   Muted:', audioTrack.isMuted);
          console.log('   MediaStreamTrack readyState:', audioTrack.mediaStreamTrack.readyState);
        }
      }, 5000);
    } catch (error) {
      console.error('❌ Failed to publish microphone:', error);
      setError(error as Error);
      throw error;
    }
  }, []);

  // 停止發布麥克風
  const unpublishMicrophone = useCallback(async () => {
    if (localAudioTrackRef.current && roomRef.current) {
      await roomRef.current.localParticipant.unpublishTrack(localAudioTrackRef.current);
      localAudioTrackRef.current.stop();
      localAudioTrackRef.current = null;
      setIsPublishing(false);
      setAgentState(prev => ({ ...prev, isListening: false }));
      setIsUserSpeaking(false); // ✅ 停止發布後不再視為正在說話
      console.log('🛑 Microphone unpublished');
    }
  }, []);

  // ✅ 手動解除靜音（處理自動播放限制）
  const unmuteAgentAudio = useCallback(async () => {
    if (roomRef.current) {
      try {
        await roomRef.current.startAudio();
        console.log('🔊 Audio playback started by user interaction');
      } catch (err) {
        console.error('❌ Failed to start audio:', err);
      }
    }
  }, []);

  // 斷開連接
  const disconnect = useCallback(async () => {
    const room = roomRef.current;
    if (room) {
      // ✅ 解除本地參與者說話事件監聽
      if (localSpeakingHandlerRef.current) {
        try {
          room.localParticipant.off(
            ParticipantEvent.IsSpeakingChanged,
            localSpeakingHandlerRef.current
          );
        } catch (e) {
          console.warn('Participant off failed (likely already disposed):', e);
        }
      }

      await room.disconnect();
      roomRef.current = null;
      setIsConnected(false);
      setIsPublishing(false);
      setAgentState({ isSpeaking: false, isListening: false });
      setIsUserSpeaking(false); // ✅ 重置
      console.log('🔌 Disconnected from room');
    }
  }, []);

  // 清理資源 - 只在組件真正卸載時清理
  useEffect(() => {
    // 不要在 dependency 變化時自動斷線
    // React StrictMode 會導致這個 effect 被多次呼叫
    return () => {
      // 只清理音訊元素，不主動斷開連接
      // 讓使用者透過按鈕控制連接狀態
      if (agentAudioElement) {
        agentAudioElement.pause();
        agentAudioElement.src = '';
      }
    };
  }, [agentAudioElement]);

  return {
    connect,
    disconnect,
    publishMicrophone,
    unpublishMicrophone,
    unmuteAgentAudio,
    isConnected,
    isPublishing,
    agentState,
    agentAudioElement,
    error,
    transcriptions,
    isUserSpeaking, // ✅ 暴露給 UI
  };
}
