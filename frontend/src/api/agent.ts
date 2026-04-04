

export const agentApi = {
  /**
   * Send a message to the agent and stream the response
   */
  sendMessage: async (msg: string): Promise<{ done: boolean }> => {
    return window.api.sendAgentMessage(msg);
  },

  /**
   * Listen to streaming chunks from the agent
   */
  onStream: (callback: (chunk: string) => void): (() => void) => {
    return window.api.onAgentStream(callback);
  },
};
