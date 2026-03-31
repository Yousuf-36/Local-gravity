export const ollamaApi = {
  /**
   * Get the list of installed models
   */
  listModels: async (): Promise<string[]> => {
    return window.api.listModels();
  },

  /**
   * Switch the active model
   */
  switchModel: async (model: string): Promise<unknown> => {
    return window.api.switchModel(model);
  },
};
